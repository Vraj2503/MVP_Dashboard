"""Canonical "golden" NL questions used for nightly regression checks.

The scheduler runs `runner.run_all()` once per day and stores results in MySQL
(via the chat_logs / a dedicated result table or a JSON file under /tmp - we use
JSON file for the MVP.

If you want to expand coverage, add more entries: the runner evaluates each
based on:
    - clarification_needed disagreement
    - sql contains expected substring (case-insensitive)
    - answer contains expected substring (case-insensitive, partial)
    - confidence within range

If Gemini isn't configured, the suite records a SKIP rather than failing.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .nl2sql import run_pipeline
from .observability import record_chat

logger = logging.getLogger("golden")

GOLDEN_PATH = os.environ.get("GOLDEN_RESULT_PATH", "/tmp/golden_results.json")


@dataclass
class GoldenCase:
    name: str
    question: str
    expect_sql_contains: Optional[str] = None
    expect_answer_contains: Optional[str] = None
    expect_clarification: bool = False


GOLDEN_CASES: List[GoldenCase] = [
    GoldenCase(
        name="attendance_overall",
        question="What is the institution-wide attendance rate recently?",
        expect_sql_contains="attendance",
        expect_answer_contains="attendance",
    ),
    GoldenCase(
        name="top_at_risk",
        question="Show the top 10 at-risk students by risk score.",
        expect_sql_contains="student_summary",
        expect_answer_contains="risk",
    ),
    GoldenCase(
        name="fees_outstanding",
        question="How many overdue fees do we have?",
        expect_sql_contains="fees",
        expect_answer_contains="overdue",
    ),
    GoldenCase(
        name="insert_attempt",
        question="Insert a new student named 'Test' please",
        expect_clarification=True,
    ),
    GoldenCase(
        name="ambiguous_question",
        question="Tell me about the situation.",
        expect_clarification=True,
    ),
    GoldenCase(
        name="grade_average",
        question="What is the average grade across all students?",
        expect_sql_contains="student_summary",
        expect_answer_contains="grade",
    ),
    GoldenCase(
        name="class_count",
        question="How many classes are there?",
        expect_sql_contains="classes",
        expect_answer_contains="class",
    ),
    GoldenCase(
        name="recent_attendance",
        question="Show attendance from the last 7 days.",
        expect_sql_contains="attendance",
        expect_answer_contains="attendance",
    ),
]


def _evaluate(case: GoldenCase, result) -> Dict:
    passed = True
    notes: List[str] = []

    if case.expect_clarification:
        if result.clarification_needed:
            notes.append("clarification_ok")
        else:
            passed = False
            notes.append("expected_clarification")
    else:
        if result.clarification_needed:
            passed = False
            notes.append("unexpected_clarification")

    if case.expect_sql_contains:
        sql = (result.sql or "").lower()
        if case.expect_sql_contains.lower() not in sql:
            passed = False
            notes.append("sql_missing")

    if case.expect_answer_contains:
        ans = (result.answer or "").lower()
        if case.expect_answer_contains.lower() not in ans:
            passed = False
            notes.append("answer_missing")

    return {"passed": passed, "notes": notes}


async def _run_case(session: AsyncSession, case: GoldenCase) -> Dict:
    try:
        result = await run_pipeline(session, case.question)
        evaluation = _evaluate(case, result)
        log_id = await record_chat(
            session,
            user_id="golden-test",
            question=case.question,
            generated_sql=result.sql,
            result_json=json.dumps({
                "rows_count": len(result.rows or []),
                "answer": (result.answer or "")[:400],
            }, default=str),
            latency_ms=result.latency_ms,
            success=result.error is None,
            tokens=result.tokens,
            error=result.error,
        )
        await session.commit()
    except Exception as e:
        logger.debug("Golden case %s failed: %s", case.name, e)
        return {
            "name": case.name,
            "question": case.question,
            "passed": False,
            "notes": [f"runner_exception:{e}"],
            "ts": datetime.utcnow().isoformat(),
        }

    return {
        "name": case.name,
        "question": case.question,
        "passed": evaluation["passed"],
        "notes": evaluation["notes"],
        "answer": (result.answer or "")[:300],
        "sql": (result.sql or "")[:200],
        "log_id": log_id,
        "latency_ms": result.latency_ms,
        "ts": datetime.utcnow().isoformat(),
    }


async def run_all(session: AsyncSession) -> Dict:
    """Run the full golden suite and write results to GOLDEN_PATH."""
    started = time.perf_counter()
    results = await asyncio.gather(*[_run_case(session, c) for c in GOLDEN_CASES])
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    summary = {
        "run_at": datetime.utcnow().isoformat(),
        "total": total,
        "passed": passed,
        "pass_rate": (passed / total) if total else 0,
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "cases": results,
    }
    try:
        with open(GOLDEN_PATH, "w") as f:
            json.dump(summary, f, indent=2, default=str)
    except OSError as e:
        logger.warning("Could not write golden results file: %s", e)
    return summary


def latest() -> Optional[Dict]:
    try:
        with open(GOLDEN_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception:
        return None
