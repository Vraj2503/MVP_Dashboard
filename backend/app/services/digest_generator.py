"""Periodic digest generator.

A digest is a JSON blob summarising the period (default: last 14 days):
- Attendance deltas at institution + per-class
- Top new At-Risk students
- Fee collection summary (paid/partial/outstanding)
- An AI narrative intro paragraph (cached for 1 hour)
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Attendance, Digest, Fee, FeeStatus, Student, StudentSummary, RiskTier,
)
from .llm_client import generate_text

logger = logging.getLogger("digest")


async def _attendance_delta(session: AsyncSession, start: date, end: date, days: int) -> Dict[str, float]:
    prior_start = start - timedelta(days=days)
    now_avg = (await session.execute(
        select(func.avg(func.if_(Attendance.status == "Present", 1.0, 0.0)))
        .where(Attendance.date >= start, Attendance.date <= end)
    )).scalar() or 0
    prior_avg = (await session.execute(
        select(func.avg(func.if_(Attendance.status == "Present", 1.0, 0.0)))
        .where(Attendance.date >= prior_start, Attendance.date < start)
    )).scalar() or 0
    return {
        "now": round(now_avg * 100, 2),
        "previous": round(prior_avg * 100, 2),
        "delta": round((now_avg - prior_avg) * 100, 2),
    }


async def _new_at_risk(session: AsyncSession, start: date, end: date) -> List[Dict]:
    q = (
        select(Student.id, Student.name, Student.grade, Student.section, StudentSummary.risk_score)
        .join(StudentSummary, StudentSummary.student_id == Student.id)
        .where(StudentSummary.risk_tier == RiskTier.AT_RISK)
        # We can't strictly bound risk by date easily, so we just return the current top 20

        .order_by(StudentSummary.risk_score.desc())
        .limit(20)
    )
    rows = (await session.execute(q)).all()
    return [
        {"student_id": r[0], "name": r[1], "grade": r[2], "section": r[3],
         "risk_score": r[4]}
        for r in rows
    ]


async def _fee_summary(session: AsyncSession, start: date, end: date) -> Dict[str, float]:
    q = select(
        func.coalesce(func.sum(Fee.amount_due), 0).label("due"),
        func.coalesce(func.sum(Fee.amount_paid), 0).label("paid"),
        func.sum(case((Fee.status == FeeStatus.OVERDUE, 1), else_=0)).label("overdue_count"),
        func.sum(case((Fee.status == FeeStatus.PAID, 1), else_=0)).label("paid_count"),
    ).where(Fee.due_date >= start, Fee.due_date <= end)
    row = (await session.execute(q)).first()
    if not row:
        return {"due": 0, "paid": 0, "outstanding": 0, "overdue_count": 0, "paid_count": 0}
    due, paid, overdue, paidc = row
    return {
        "due": float(due or 0),
        "paid": float(paid or 0),
        "outstanding": float((due or 0) - (paid or 0)),
        "overdue_count": int(overdue or 0),
        "paid_count": int(paidc or 0),
    }


async def _narrative(content: Dict) -> str:
    prompt = (
        "Write a 90-140 word executive digest for a school admin. "
        "Lead with the most important movement. Concrete numbers only.\n\n"
        f"{json.dumps(content, default=str)}"
    )
    try:
        return (await generate_text(prompt, temperature=0.4, max_tokens=300)).strip()
    except Exception as e:
        logger.debug("Digest narrative fallback: %s", e)
        att = content.get("attendance", {})
        return (
            f"Attendance is at {att.get('now', '?')}% ({att.get('delta', '?')} pts). "
            "See top at-risk list and fee summary below."
        )


async def generate_digest(session: AsyncSession, *, days: int = 14, start_date: Optional[date] = None, end_date: Optional[date] = None) -> Digest:
    if start_date and end_date:
        start = start_date
        end = end_date
        days = (end - start).days or 1
    else:
        end = date.today()
        start = end - timedelta(days=days)

    attendance = await _attendance_delta(session, start, end, days)
    new_at_risk = await _new_at_risk(session, start, end)
    fees = await _fee_summary(session, start, end)

    content: Dict = {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "attendance": attendance,
        "new_at_risk": new_at_risk,
        "fees": fees,
    }
    content["narrative"] = await _narrative(content)

    digest = Digest(
        period_start=start,
        period_end=end,
        content_json=json.dumps(content, default=str),
    )
    session.add(digest)
    await session.flush()
    return digest
