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

_cached_schema_ddl = ""

async def load_schema_ddl(engine) -> None:
    global _cached_schema_ddl
    ddl_parts = []
    try:
        async with engine.connect() as conn:
            for table in settings.allowed_tables_list:
                try:
                    result = await conn.execute(text(f"SHOW CREATE TABLE {table}"))
                    row = result.fetchone()
                    if row:
                        create_stmt = row[1]
                        # simplify the DDL for the LLM to save tokens
                        create_stmt = re.sub(r' ENGINE=.*', ';', create_stmt)
                        create_stmt = re.sub(r' AUTO_INCREMENT=\d+', '', create_stmt)
                        ddl_parts.append(create_stmt)
                except Exception as e:
                    logger.warning(f"Could not load schema for {table}: {e}")
        _cached_schema_ddl = "\n".join(ddl_parts)
        logger.info("Schema DDL auto-synced from DB successfully.")
    except Exception as e:
        logger.error(f"Failed to auto-sync schema DDL: {e}")

def get_system_prompt() -> str:
    schema_ddl = _cached_schema_ddl or "Schema not loaded."
    return f"""You are a friendly and expert SQL generator for a school management dashboard.
The user can ONLY ask read-only questions; never generate writes.

Allowed tables (use these exact names):
{", ".join(t for t in settings.allowed_tables_list)}

Database schema (MySQL 8):
{schema_ddl}

SCHEMA ANNOTATIONS (read before generating SQL):
- students: name (full name), grade (school year 9-12 NOT academic score), section (A-E), gender, dob, parent_contact
- attendance: student_id, date, status, period. NO class_id column. Filter by grade/section via students table.
- attendance.status exact values: 'Present', 'Absent', 'Late', 'Excused', 'Holiday'
- assessments: student_id, subject, type (Quiz|Midterm|Final|Project), score, max_score, date
- assignments: student_id, title, submitted (bool), on_time (bool), score, due_date
- fees: student_id, term, amount_due, amount_paid, due_date, status ENUM (Paid|Partial|Unpaid|Overdue)
- student_summary: pre-computed per-student stats. attendance_rate (float 0-1), grade_avg (0-100), risk_score, risk_tier (Safe|Watch|At-Risk)
- classes: id, name, grade, section, teacher_id. teachers: id, name, subject.
- To find a student's class, JOIN classes ON students.grade = classes.grade AND students.section = classes.section. (Do NOT join on id)

Return STRICT JSON. The single allowed shape is:
{{
  "sql": "<a single SELECT statement; no trailing semicolon>",
  "explanation": "<one-sentence plain-English intent>",
  "confidence": <float 0..1>
}}

COLUMN MAPPING RULES (CRITICAL — follow these exactly):
- "attendance" or "attendance rate" OVERALL → student_summary.attendance_rate (FLOAT 0-1)
- "attendance" on a SPECIFIC DATE → attendance.status ('Present', 'Absent', 'Late', 'Excused', 'Holiday') joined with attendance.date
- "grades", "GPA", "academic performance" → student_summary.grade_avg (FLOAT 0-100)
- "risk", "at_risk" → student_summary.risk_score or risk_tier
- "missing assignments" → student_summary.assignment_miss_rate
- "fee", "overdue" → student_summary.fee_overdue_factor or fees table
- "unpaid", "unpaid fees", "not paid" → fees.status = 'OVERDUE'
- "grade" (as in school year, e.g., "grade 10") → students.grade (INT)

BUSINESS TERM → SQL PATTERN RULES (follow exactly):
- "attendance rate/%" from raw data = SUM(CASE WHEN a.status='Present' THEN 1.0 ELSE 0.0 END)/COUNT(a.id)*100
- "100%/perfect attendance" = GROUP BY student HAVING SUM(CASE WHEN status!='Present' THEN 1 ELSE 0 END)=0 AND COUNT(id)>=1
- "never absent" = NOT EXISTS (SELECT 1 FROM attendance WHERE student_id=s.id AND status='Absent')
- "weighted average" = SUM(score)/SUM(max_score)*100, NOT AVG(score/max_score)*100
- "no X" or "zero Y" = LEFT JOIN + IS NULL or NOT EXISTS. NEVER INNER JOIN for missing-data queries.
- "more X than Y" (statuses) = HAVING SUM(CASE WHEN status='X' THEN 1 ELSE 0 END) > SUM(CASE WHEN status='Y' THEN 1 ELSE 0 END)
- "days" (e.g., "how many days") = COUNT(DISTINCT date), NOT COUNT(id)
- Always use 1.0 in CASE for division to prevent integer truncation.
- Row filters → WHERE. Aggregate filters → HAVING.

FEW-SHOT EXAMPLES:
Q: "What class is Adam Sellers in?"
SQL: SELECT c.name FROM students s JOIN classes c ON s.grade = c.grade AND s.section = c.section WHERE s.name LIKE '%Adam Sellers%'

Q: "Top 10 students with highest attendance"
SQL: SELECT s.name, ss.attendance_rate FROM students s JOIN student_summary ss ON s.id = ss.student_id ORDER BY ss.attendance_rate DESC LIMIT 10

Q: "Students with lowest grades"
SQL: SELECT s.name, ss.grade_avg FROM students s JOIN student_summary ss ON s.id = ss.student_id ORDER BY ss.grade_avg ASC LIMIT 10

Q: "What was the attendance percent of class 10 B on 4 june 2026?"
SQL: SELECT SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) / COUNT(a.id) * 100 AS attendance_percent FROM attendance a JOIN students s ON a.student_id = s.id WHERE s.grade = 10 AND s.section = 'B' AND a.date = '2026-06-04'

Q: "Fee defaulters in grade 10"
SQL: SELECT s.name, f.amount_due, f.amount_paid, f.status FROM students s JOIN fees f ON s.id = f.student_id WHERE s.grade = 10 AND f.status = 'Overdue'

Q: "What is the attendance percentage for grade 10?"
SQL: SELECT SUM(CASE WHEN a.status = 'Present' THEN 1.0 ELSE 0.0 END) / COUNT(a.id) * 100 AS attendance_pct FROM attendance a JOIN students s ON a.student_id = s.id WHERE s.grade = 10

Q: "List students with 100% attendance who have at least 3 attendance records"
SQL: SELECT s.name FROM students s JOIN attendance a ON s.id = a.student_id GROUP BY s.id, s.name HAVING COUNT(a.id) >= 3 AND SUM(CASE WHEN a.status != 'Present' THEN 1 ELSE 0 END) = 0

Q: "Students who have never been absent"
SQL: SELECT s.name FROM students s WHERE NOT EXISTS (SELECT 1 FROM attendance a WHERE a.student_id = s.id AND a.status = 'Absent')

Q: "How many students were absent on 4 June 2026?"
SQL: SELECT COUNT(DISTINCT a.student_id) AS absent_count FROM attendance a WHERE a.date = '2026-06-04' AND a.status = 'Absent'

Q: "Students with more absences than present days"
SQL: SELECT s.name, SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absences, SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS presents FROM students s JOIN attendance a ON s.id = a.student_id GROUP BY s.id, s.name HAVING SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) > SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END)

Q: "Overall percentage score for John in Math"
SQL: SELECT s.name, SUM(a.score) / SUM(a.max_score) * 100 AS weighted_avg FROM students s JOIN assessments a ON s.id = a.student_id WHERE s.name LIKE '%John%' AND a.subject LIKE '%Math%' GROUP BY s.id, s.name

Q: "Top 3 students by grade average in each grade level"
SQL: SELECT name, grade, grade_avg FROM (SELECT s.name, s.grade, ss.grade_avg, ROW_NUMBER() OVER (PARTITION BY s.grade ORDER BY ss.grade_avg DESC) AS rn FROM students s JOIN student_summary ss ON s.id = ss.student_id) ranked WHERE rn <= 3

Q: "At-risk students with attendance below 70% and overdue fees"
SQL: SELECT s.name, ss.attendance_rate, ss.risk_tier, f.status FROM students s JOIN student_summary ss ON s.id = ss.student_id JOIN fees f ON s.id = f.student_id WHERE ss.risk_tier = 'At-Risk' AND ss.attendance_rate < 0.70 AND f.status = 'Overdue'

Q: "Students with attendance rate above school average"
SQL: SELECT s.name, ss.attendance_rate FROM students s JOIN student_summary ss ON s.id = ss.student_id WHERE ss.attendance_rate > (SELECT AVG(attendance_rate) FROM student_summary)

Q: "Daily attendance trend for grade 10 in last 30 days"
SQL: SELECT a.date, SUM(CASE WHEN a.status = 'Present' THEN 1.0 ELSE 0.0 END) / COUNT(a.id) * 100 AS daily_pct FROM attendance a JOIN students s ON a.student_id = s.id WHERE s.grade = 10 AND a.date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) GROUP BY a.date ORDER BY a.date

Q: "How many distinct subjects has each student been assessed in?"
SQL: SELECT s.name, COUNT(DISTINCT a.subject) AS subject_count FROM students s JOIN assessments a ON s.id = a.student_id GROUP BY s.id, s.name ORDER BY subject_count DESC

Q: "Students whose grade average is below their class average"
SQL: SELECT s.name, ss.grade_avg, s.grade, s.section FROM students s JOIN student_summary ss ON s.id = ss.student_id WHERE ss.grade_avg < (SELECT AVG(ss2.grade_avg) FROM student_summary ss2 JOIN students s2 ON ss2.student_id = s2.id WHERE s2.grade = s.grade AND s2.section = s.section)

Q: "Students with attendance below 80% and more than 2 missed assignments"
SQL: SELECT s.name, ss.attendance_rate, COUNT(a.id) AS missed FROM students s JOIN student_summary ss ON s.id = ss.student_id JOIN assignments a ON s.id = a.student_id WHERE ss.attendance_rate < 0.80 AND a.submitted = 0 GROUP BY s.id, s.name, ss.attendance_rate HAVING COUNT(a.id) > 2

IMPORTANT: When generating SQL, ALWAYS include any columns you filter or sort by in the SELECT clause.
IMPORTANT: When searching for names or text strings, ALWAYS use `LIKE '%...%'` with wildcards instead of exact equality (`=`).
IMPORTANT: For overall metrics like average attendance, grades, or risk, join with the `student_summary` table and use pre-calculated columns.
IMPORTANT: When asked for attendance on a *specific date*, query the `attendance` table directly using the `date` column. Do not use `student_summary` for specific dates.

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

    prompt = f"{get_system_prompt()}{history_prompt}\n\nUser question: {question.strip()}\nReturn JSON only."
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
    """Layer 1: Deterministic post-processing to fix common LLM mistakes.

    This runs BEFORE execution and catches:
      - Enum value mismatches (case, hyphens, underscores)
      - Column name hallucinations (e.g., 'grade' instead of 'grade_avg')
    """
    if not sql:
        return sql

    # ── Enum Normalization ──────────────────────────────────────────────
    # Map every plausible LLM variation → exact DB value.
    _ENUM_CANONICAL: Dict[str, Dict[str, str]] = {
        # risk_tier column
        "risk_tier": {
            "at-risk": "AT_RISK", "at_risk": "AT_RISK", "atrisk": "AT_RISK",
            "high": "AT_RISK", "high risk": "AT_RISK", "at risk": "AT_RISK",
            "safe": "SAFE", "low": "SAFE", "low risk": "SAFE",
            "watch": "WATCH", "medium": "WATCH", "moderate": "WATCH",
        },
        # fees.status column
        "status": {
            "overdue": "OVERDUE", "over due": "OVERDUE", "over_due": "OVERDUE",
            "unpaid": "OVERDUE", "not paid": "OVERDUE",
            "paid": "PAID", "partial": "PARTIAL",
        },
        # attendance.status column
        "attendance_status": {
            "present": "Present", "absent": "Absent", "late": "Late",
        },
    }

    def _fix_enum(match: re.Match) -> str:
        col = match.group("col").strip().lower()
        quote = match.group("quote")  # ' or "
        val = match.group("val")

        # Determine which enum map to use based on the column name
        lookup = None
        if "risk" in col:
            lookup = _ENUM_CANONICAL["risk_tier"]
        elif "status" in col:
            # Could be fee status or attendance status; fee status is more common in queries
            lookup = _ENUM_CANONICAL["status"]

        if lookup:
            normalised = val.strip().lower().replace("-", "").replace("_", "").replace(" ", "")
            for variant, canonical in lookup.items():
                if normalised == variant.replace("-", "").replace("_", "").replace(" ", ""):
                    return f"{match.group('col')}{match.group('op')}{quote}{canonical}{quote}"

        return match.group(0)  # no change

    # Regex: captures  column_name = 'value'  or  column_name IN ('value', ...)
    sql = re.sub(
        r"(?P<col>\b\w+(?:\.\w+)?)\s*(?P<op>=|!=|<>|LIKE)\s*(?P<quote>['\"])(?P<val>[^'\"]+)(?P=quote)",
        _fix_enum,
        sql,
        flags=re.IGNORECASE,
    )

    # Also handle IN (...) clauses: fix each literal inside
    def _fix_in_clause(match: re.Match) -> str:
        col = match.group("col").strip().lower()
        in_body = match.group("body")

        lookup = None
        if "risk" in col:
            lookup = _ENUM_CANONICAL["risk_tier"]
        elif "status" in col:
            lookup = _ENUM_CANONICAL["status"]

        if not lookup:
            return match.group(0)

        def _replace_literal(lit_match: re.Match) -> str:
            quote = lit_match.group(1)
            val = lit_match.group(2)
            normalised = val.strip().lower().replace("-", "").replace("_", "").replace(" ", "")
            for variant, canonical in lookup.items():
                if normalised == variant.replace("-", "").replace("_", "").replace(" ", ""):
                    return f"{quote}{canonical}{quote}"
            return lit_match.group(0)

        fixed_body = re.sub(r"(['\"])([^'\"]+)\1", _replace_literal, in_body)
        return f"{match.group('col')} IN ({fixed_body})"

    sql = re.sub(
        r"(?P<col>\b\w+(?:\.\w+)?)\s+IN\s*\((?P<body>[^)]+)\)",
        _fix_in_clause,
        sql,
        flags=re.IGNORECASE,
    )

    # ── Column Name Fixes ───────────────────────────────────────────────
    # Only apply in SELECT/WHERE/ORDER BY contexts (not table aliases)

    # Fix: 'grade' used as academic performance → 'grade_avg'
    # But NOT when it's students.grade (school year) or s.grade
    # Strategy: if it's in ORDER BY, WHERE with comparison operators, and NOT prefixed by s. or students.
    sql = re.sub(
        r'(?<!\w)(?<!s\.)(?<!students\.)(?<!student_summary\.)\bgrade\b(?!_)(?!\s+(?:INT|VARCHAR|=\s*\d))',
        lambda m: 'grade_avg' if any(kw in sql.lower()[:sql.lower().find(m.group())] for kw in ['order by', 'where', 'having', 'select']) and 'student_summary' in sql.lower() else m.group(),
        sql
    )

    # Fix: bare 'attendance' → 'attendance_rate' when used with student_summary
    sql = re.sub(
        r'(?<!\w)(?<!\.)\battendance\b(?!_)(?!\s)',
        lambda m: 'attendance_rate' if 'student_summary' in sql.lower() else m.group(),
        sql,
        flags=re.IGNORECASE,
    )

    # ── Integer Division Guard ───────────────────────────────────────────
    # CASE THEN 1 ELSE 0 → THEN 1.0 ELSE 0.0 to prevent MySQL integer division
    sql = re.sub(
        r'THEN\s+1\s+ELSE\s+0(?!\.)',
        'THEN 1.0 ELSE 0.0',
        sql,
        flags=re.IGNORECASE,
    )

    return sql


async def _schema_validate_enums(session: AsyncSession, sql: str) -> str:
    """Layer 2: Schema-aware validation. Query the DB for actual enum values
    and correct any remaining mismatches after the deterministic rewriter.

    Only fires when the SQL references known enum columns.
    """
    enum_columns = {
        "risk_tier": "student_summary",
        "status": "fees",
    }

    for col, table in enum_columns.items():
        # Check if this column appears in the SQL
        if col not in sql.lower():
            continue

        try:
            result = await session.execute(
                text(f"SELECT DISTINCT {col} FROM {table} LIMIT 20")
            )
            actual_values = [str(row[0]) for row in result if row[0] is not None]
        except Exception:
            continue

        if not actual_values:
            continue

        # Build a case-insensitive lookup: normalised → actual
        actual_map = {}
        for v in actual_values:
            key = v.lower().replace("-", "").replace("_", "").replace(" ", "")
            actual_map[key] = v

        # Find string literals in the SQL that are compared against this column
        pattern = re.compile(
            rf"\b{col}\b\s*(?:=|!=|<>|LIKE)\s*['\"]([^'\"]+)['\"]",
            re.IGNORECASE,
        )
        for m in pattern.finditer(sql):
            found_val = m.group(1)
            normalised = found_val.lower().replace("-", "").replace("_", "").replace(" ", "")
            if normalised in actual_map and found_val != actual_map[normalised]:
                sql = sql.replace(found_val, actual_map[normalised])
                logger.info("Schema validator fixed enum: '%s' → '%s'", found_val, actual_map[normalised])

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


async def _retry_with_error(question: str, failed_sql: str, error_msg: str, session_history: List[Any] = None) -> Dict[str, Any]:
    """Layer 3: If execution fails, feed the error back to the LLM for one self-correction attempt."""
    retry_prompt = (
        f"{get_system_prompt()}\n\n"
        f"User question: {question.strip()}\n\n"
        f"Your PREVIOUS SQL attempt was:\n{failed_sql}\n\n"
        f"It FAILED with this error:\n{error_msg}\n\n"
        "Please fix the SQL and try again. Common issues:\n"
        "- Wrong enum values (check the schema DDL for exact column types)\n"
        "- Wrong column names (e.g., 'grade' vs 'grade_avg')\n"
        "- Missing JOINs\n\n"
        "Return JSON only."
    )
    return await generate_json(retry_prompt)


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

    # ── Layer 1: Deterministic SQL Rewriter ──
    sql = _rewrite_sql(sql)

    # ── Layer 2: Schema-Aware Enum Validation ──
    try:
        sql = await _schema_validate_enums(session, sql)
    except Exception as e:
        logger.warning("Schema enum validation failed (non-fatal): %s", e)

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
        # ── Layer 3: LLM Self-Correction Retry ──
        logger.warning("First SQL attempt failed (%s), retrying with error feedback...", e)
        try:
            retry_plan = await _retry_with_error(question, sql, str(e), session_history)
            retry_sql = (retry_plan.get("sql") or "").strip()
            if retry_sql:
                retry_sql = _rewrite_sql(retry_sql)
                try:
                    retry_sql = await _schema_validate_enums(session, retry_sql)
                except Exception:
                    pass
                ok2, why2 = _validate_sql(retry_sql)
                if ok2:
                    try:
                        columns, rows = await _execute_sql(session, retry_sql)
                        sql = retry_sql
                        explanation = retry_plan.get("explanation") or explanation
                        logger.info("Retry succeeded with corrected SQL.")
                    except Exception as e2:
                        return PipelineResult(
                            answer="I'm really sorry, I tried running that query but something went wrong on my end.",
                            sql=retry_sql,
                            confidence=confidence,
                            error=f"retry_execution_failed:{e2}",
                            latency_ms=int((time.perf_counter() - started) * 1000),
                        )
                else:
                    return PipelineResult(
                        answer="I'm sorry, I couldn't generate a valid query for that.",
                        sql=retry_sql, confidence=confidence,
                        error=f"retry_validation_failed:{why2}",
                        latency_ms=int((time.perf_counter() - started) * 1000),
                    )
            else:
                return PipelineResult(
                    answer="I'm really sorry, I tried running that query but something went wrong on my end.",
                    sql=sql, confidence=confidence,
                    error=f"execution_failed:{e}",
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
        except Exception:
            return PipelineResult(
                answer="I'm really sorry, I tried running that query but something went wrong on my end.",
                sql=sql, confidence=confidence,
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
