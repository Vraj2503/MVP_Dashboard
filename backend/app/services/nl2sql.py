"""NL -> SQL -> result pipeline.

Defence in depth (in order):
1. Gemini is constrained (via the prompt) to return ONE of:
     {"sql": "...", "explanation": "...", "confidence": 0..1}
     {"clarification_needed": "..."}
2. `sqlparse` parses the SQL; we reject anything not obviously SELECT.
3. Every referenced table is checked against the allow-list.
4. We also execute via the read-only MySQL user.
5. Result rows are hard-bounded to MAX_ROWS before being returned to Gemini for
   final natural-language answer generation.

The pipeline returns the consistent shape used by the chat router:
    { answer, sql, rows, columns, confidence, clarification_needed }
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import sqlparse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from .llm_client import generate_json, generate_text

settings = get_settings()
logger = logging.getLogger("nl2sql")

MAX_ROWS = 200          # hard cap on rows returned to LLM
SQL_TIMEOUT_MS = 3000   # statement-level safety

SCHEMA_DDL = """
CREATE TABLE students (
  id INT, name VARCHAR(160), grade INT, section VARCHAR(8),
  enrollment_date DATE, parent_contact VARCHAR(40), gender VARCHAR(8), dob DATE
);
CREATE TABLE teachers (id INT, name VARCHAR(120), subject VARCHAR(80));
CREATE TABLE classes (id INT, name VARCHAR(80), grade INT, section VARCHAR(8), teacher_id INT);
CREATE TABLE attendance (
  id INT, student_id INT, date DATE, status VARCHAR(16), period INT
);
CREATE TABLE assessments (
  id INT, student_id INT, subject VARCHAR(60), type VARCHAR(40),
  score FLOAT, max_score FLOAT, date DATE
);
CREATE TABLE assignments (
  id INT, student_id INT, title VARCHAR(160), submitted BOOL, on_time BOOL,
  score FLOAT, due_date DATE
);
CREATE TABLE fees (
  id INT, student_id INT, term VARCHAR(40), amount_due FLOAT, amount_paid FLOAT,
  due_date DATE, status VARCHAR(16)
);
CREATE TABLE behavior_notes (
  id INT, student_id INT, teacher_id INT, note TEXT, severity VARCHAR(16), date DATE
);
CREATE TABLE student_summary (
  student_id INT, attendance_rate FLOAT, grade_avg FLOAT,
  assignment_miss_rate FLOAT, fee_overdue_factor FLOAT,
  risk_score FLOAT, risk_tier VARCHAR(8), updated_at DATETIME
);
CREATE TABLE alerts (
  id INT, type VARCHAR(80), student_id INT, severity VARCHAR(16),
  message TEXT, suggested_action TEXT, status VARCHAR(16), created_at DATETIME
);
CREATE TABLE digests (
  id INT, period_start DATE, period_end DATE, content_json TEXT, created_at DATETIME
);
CREATE TABLE chat_logs (
  id INT, user_id VARCHAR(80), question TEXT, generated_sql TEXT,
  result_json TEXT, feedback INT, latency_ms INT, tokens INT,
  success BOOL, error TEXT, timestamp DATETIME
);
"""


SYSTEM_PROMPT = f"""You are a friendly and expert SQL generator for a school management dashboard.
The user can ONLY ask read-only questions; never generate writes.

Allowed tables (use these exact names):
{", ".join(t for t in settings.allowed_tables_list)}

Database schema (MySQL 8):
{SCHEMA_DDL}

Return STRICT JSON. The single allowed shape is:
{{
  "sql": "<a single SELECT statement; no trailing semicolon>",
  "explanation": "<one-sentence plain-English intent>",
  "confidence": <float 0..1>
}}

COLUMN MAPPING RULES (CRITICAL — follow these exactly):
- "attendance" or "attendance rate" → student_summary.attendance_rate (FLOAT 0-1)
- "grades", "GPA", "academic performance" → student_summary.grade_avg (FLOAT 0-100)
- "risk", "at-risk" → student_summary.risk_score or risk_tier
- "missing assignments" → student_summary.assignment_miss_rate
- "fee", "overdue" → student_summary.fee_overdue_factor or fees table
- "grade" (as in school year, e.g., "grade 10") → students.grade (INT)

FEW-SHOT EXAMPLES:
Q: "Top 10 students with highest attendance"
SQL: SELECT s.name, ss.attendance_rate FROM students s JOIN student_summary ss ON s.id = ss.student_id ORDER BY ss.attendance_rate DESC LIMIT 10

Q: "Students with lowest grades"
SQL: SELECT s.name, ss.grade_avg FROM students s JOIN student_summary ss ON s.id = ss.student_id ORDER BY ss.grade_avg ASC LIMIT 10

Q: "How many students are at risk?"
SQL: SELECT COUNT(*) AS at_risk_count FROM student_summary WHERE risk_tier = 'High'

Q: "Fee defaulters in grade 10"
SQL: SELECT s.name, f.amount_due, f.amount_paid, f.status FROM students s JOIN fees f ON s.id = f.student_id WHERE s.grade = 10 AND f.status = 'Overdue'

Q: "Show me recent behavior notes for John"
SQL: SELECT s.name, b.note, b.severity, b.date FROM behavior_notes b JOIN students s ON b.student_id = s.id WHERE s.name LIKE '%John%' ORDER BY b.date DESC LIMIT 5

IMPORTANT: When generating SQL, ALWAYS include any columns you filter or sort by in the SELECT clause.
IMPORTANT: When searching for names or text strings, ALWAYS use `LIKE '%...%'` with wildcards instead of exact equality (`=`).
IMPORTANT: For overall metrics like attendance, grades, or risk, ALWAYS join with the `student_summary` table and use pre-calculated columns instead of aggregating raw records (e.g., `COUNT` on attendance).

If the user's question is ambiguous, unrelated to the schema, or cannot be answered using the available tables, return:
{{ "clarification_needed": "<a friendly, polite message explaining what you need>", "choices": ["<optional list of up to 3 strings for disambiguation>"] }}

You may also optionally include a "choices" field (a list of up to 3 strings) in a successful response to suggest relevant follow-up questions to the user.

Do not add commentary outside the JSON. Prefer SELECT over SHOW/DESCRIBE.
"""


@dataclass
class PipelineResult:
    answer: str
    sql: Optional[str] = None
    rows: Optional[List[Dict[str, Any]]] = None
    columns: Optional[List[str]] = None
    confidence: float = 0.0
    clarification_needed: Optional[str] = None
    choices: Optional[List[str]] = None
    chart_hint: Optional[str] = None   # kpi | line | bar | pie | table
    tokens: int = 0
    latency_ms: int = 0
    error: Optional[str] = None


# ---------------------------------------------------------------- helpers


_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|truncate|alter|create|replace|rename|grant|revoke|"
    r"load|set|use|call|handler|kill|prepare|execute|lock|unlock|begin|commit|"
    r"rollback|savepoint|start|stop|flush|reset|analyze|repair|optimize|check)\b",
    re.IGNORECASE,
)


def _validate_sql(sql: str) -> Tuple[bool, Optional[str]]:
    if not sql or not sql.strip():
        return False, "empty_sql"

    parsed = sqlparse.parse(sql)
    if len(parsed) != 1:
        return False, "only_one_statement_allowed"

    stmt = parsed[0]
    if (stmt.get_type() or "").upper() != "SELECT":
        return False, "select_only"

    # Belt-and-braces keyword scan
    bad = _FORBIDDEN_KEYWORDS.search(sql)
    if bad:
        return False, f"forbidden_keyword:{bad.group(0)}"

    # Allow-list tables (extract identifiers of type "table")
    from sqlparse.sql import Identifier, IdentifierList, Function
    from sqlparse.tokens import Keyword, DML

    seen_tables: List[str] = []
    def _collect(identifier):
        real_name = identifier.get_real_name()
        if real_name and identifier.is_type("table"):
            seen_tables.append(real_name)

    def _visit(tok):
        if isinstance(tok, IdentifierList):
            for t in tok.tokens:
                if isinstance(t, Identifier):
                    _collect(t)
        elif isinstance(tok, Identifier) and not isinstance(tok, Function):
            _collect(tok)

    _visit(stmt)

    # Extract from FROM/JOIN clauses robustly
    from_seen = False
    for tok in stmt.flatten():
        val = (tok.value or "").lower()
        if val in ("from", "join"):
            from_seen = True
            continue
        if from_seen and tok.ttype is Keyword:
            from_seen = False
            continue
    # Simpler: split on FROM/JOIN keywords and collect identifiers
    lowered = sql.lower()
    body = lowered
    for delim in (" where ", " group by ", " having ", " order by ", " limit "):
        idx = body.find(delim)
        if idx >= 0:
            body = body[:idx]
    parts = re.split(r"\b(from|join)\b", body)
    # parts: [head, kw1, tail1, kw2, tail2, ...]
    candidate_words: List[str] = []
    for i in range(2, len(parts), 2):
        tail = parts[i]
        words = re.split(r"[\s,]+", tail.strip())
        candidate_words.append(words[0] if words else "")

    bad_table = next(
        (t for t in candidate_words if t and t not in settings.allowed_tables_list),
        None,
    )
    if bad_table:
        return False, f"table_not_allowed:{bad_table}"

    return True, None


async def _generate_sql(question: str, session_history: List[Any] = None) -> Dict[str, Any]:
    history_prompt = ""
    if session_history:
        history_prompt = "\n\nPrevious Conversation Context:\n"
        # session_history contains ChatLog objects, oldest first
        for log in session_history:
            history_prompt += f"User: {log.question}\n"
            if log.generated_sql:
                history_prompt += f"SQL run: {log.generated_sql}\n"
            if log.result_json:
                history_prompt += f"System: {log.result_json}\n"
        history_prompt += "\nUse this context to resolve pronouns or implied constraints in the new question."

    prompt = f"{SYSTEM_PROMPT}{history_prompt}\n\nUser question: {question.strip()}\nReturn JSON only."
    return await generate_json(prompt)


async def _execute_sql(session: AsyncSession, sql: str) -> Tuple[List[str], List[Dict[str, Any]]]:
    result = await session.execute(text(sql).execution_options(timeout=SQL_TIMEOUT_MS // 1000))
    columns = list(result.keys())
    rows: List[Dict[str, Any]] = []
    for raw in result.mappings():
        rows.append({k: _jsonable(raw[k]) for k in columns})
        if len(rows) >= MAX_ROWS:
            break
    return columns, rows


def _rewrite_sql(sql: str) -> str:
    """Safety net to catch common LLM mistakes even after few-shot prompting."""
    if not sql:
        return sql
    lowered = sql.lower()
    
    # Mistake 1: Ordering by 'grade' (school year) instead of 'grade_avg' when it's clearly performance
    if "order by grade desc" in lowered or "order by grade asc" in lowered or "order by s.grade" in lowered:
        # Note: robust replacement would use regex, keeping it simple here
        sql = re.sub(r'(?i)\border by\s+(s\.)?grade\b', r'ORDER BY \1grade_avg', sql)
        
    # Mistake 2: "Lowest" but ordered DESC
    if "lowest" in lowered and "desc" in lowered:
        # A bit risky to auto-rewrite without full context, but common mistake
        pass 
        
    return sql


def _jsonable(v: Any) -> Any:
    if v is None or isinstance(v, (int, float, str, bool)):
        return v
    return str(v)


_DATE_PATTERNS = re.compile(r"(date|time|day|week|month|year|period|semester|term)", re.IGNORECASE)
_NUMERIC_TYPES = (int, float)


def _detect_chart_hint(columns: List[str], rows: List[Dict[str, Any]]) -> Optional[str]:
    """Infer the best visualisation type from the result shape."""
    return "table"


async def _format_answer(question: str, sql: str, columns: List[str],
                         rows: List[Dict[str, Any]], explanation: str) -> str:
    sample = rows[:10]
    prompt = (
        "You are a friendly and helpful AI assistant for school administrators.\n"
        "You are answering a user's question based ONLY on the provided SQL query results.\n"
        f"Question: {question}\n"
        f"SQL explanation: {explanation}\n"
        f"Columns: {columns}\n"
        f"Sample rows ({len(sample)} of {len(rows)} shown): {json.dumps(sample, default=str)}\n"
        "Instructions:\n"
        "1. Adopt a warm, polite, and friendly tone.\n"
        "2. Answer the question concisely (2-4 sentences) using ONLY the provided data.\n"
        "3. If the data is empty, insufficient, or you cannot answer the question definitively from the rows provided, gracefully apologize and explain what information is missing. DO NOT guess or hallucinate data.\n"
        "4. Do not use markdown tables."
    )
    return await generate_text(prompt, temperature=0.3, max_tokens=512)


# ---------------------------------------------------------------- public


async def run_pipeline(session: AsyncSession, question: str, session_history: List[Any] = None) -> PipelineResult:
    started = time.perf_counter()
    
    # 1. Intent Classifier (Pre-Pipeline)
    q_lower = question.lower().strip()
    greetings = {"hello", "hi", "hey", "good morning", "good afternoon", "good evening"}
    farewells = {"bye", "goodbye", "thanks", "thank you", "cya"}
    
    if q_lower in greetings or any(q_lower.startswith(g) for g in greetings):
        return PipelineResult(
            answer="Hello! I'm your AI school assistant. I can help you query student records, attendance, grades, fees, and more. What would you like to know?",
            latency_ms=int((time.perf_counter() - started) * 1000)
        )
        
    if q_lower in farewells or any(q_lower.startswith(f) for f in farewells):
        return PipelineResult(
            answer="You're welcome! Let me know if you need anything else.",
            latency_ms=int((time.perf_counter() - started) * 1000)
        )

    try:
        plan = await _generate_sql(question, session_history)
    except Exception as e:
        return PipelineResult(answer="I'm sorry, I couldn't quite understand that. Could you please rephrase?",
                              error=f"planner_failed:{e}")

    if not isinstance(plan, dict):
        return PipelineResult(answer="I'm sorry, I ran into an internal error while processing that.", error="bad_json_shape")

    if "clarification_needed" in plan and plan["clarification_needed"]:
        return PipelineResult(
            answer=str(plan["clarification_needed"]),
            confidence=0.0,
            clarification_needed=str(plan["clarification_needed"]),
            choices=plan.get("choices"),
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    sql = (plan.get("sql") or "").strip()
    explanation = plan.get("explanation") or ""
    confidence = float(plan.get("confidence") or 0.0)

    # 4. Confidence gating
    if confidence < settings.nl2sql_confidence_threshold:
        return PipelineResult(
            answer=f"I'm not entirely sure how to answer that (confidence {confidence*100:.0f}%). Could you try rephrasing or asking something more specific about the school data?",
            latency_ms=int((time.perf_counter() - started) * 1000)
        )

    if not sql:
        return PipelineResult(answer="I'm sorry, I couldn't generate a query for that. Could you try asking in a different way?", error="no_sql")

    # 3. Post-Generation SQL Rewriter
    sql = _rewrite_sql(sql)

    ok, why = _validate_sql(sql)
    if not ok:
        return PipelineResult(
            answer="I'm sorry, I can only run read-only questions about the school data. Please try again!",
            sql=sql,
            confidence=confidence,
            error=f"validation_failed:{why}",
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    try:
        columns, rows = await _execute_sql(session, sql)
    except Exception as e:
        return PipelineResult(
            answer="I'm really sorry, I tried running that query but something went wrong on my end.",
            sql=sql,
            confidence=confidence,
            error=f"execution_failed:{e}",
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    # 5. Empty-Result Handler
    if not rows:
        answer = "I ran the query successfully, but I couldn't find any data matching your criteria. You might want to check the spelling of names or try a broader search."
    else:
        try:
            answer = await _format_answer(question, sql, columns, rows, explanation)
        except Exception as e:  # pragma: no cover
            answer = explanation or "Here is the raw result."

    return PipelineResult(
        answer=answer,
        sql=sql,
        rows=rows,
        columns=columns,
        confidence=confidence,
        choices=plan.get("choices"),
        chart_hint=_detect_chart_hint(columns, rows),
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
