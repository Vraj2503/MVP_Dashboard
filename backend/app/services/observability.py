"""Observability for NL2SQL interactions.

Persists every chat call to `chat_logs` (latency, tokens, success, error),
records thumbs up/down feedback, and exposes summary metrics (M12) used by
the admin /observability page:
    - total_queries
    - success_rate
    - avg_latency_ms
    - failed_queries
    - feedback_ratio (= thumbs-up / (thumbs-up + thumbs-down))
    - golden_pass_rate (from golden_tests.last_run)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func, case, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ChatLog

logger = logging.getLogger("observability")


async def record_chat(
    session: AsyncSession,
    *,
    user_id: Optional[str],
    question: str,
    generated_sql: Optional[str],
    result_json: Optional[str],
    latency_ms: int,
    success: bool,
    tokens: int = 0,
    error: Optional[str] = None,
    session_id: Optional[str] = None
) -> int:
    row = ChatLog(
        user_id=user_id,
        question=question,
        generated_sql=generated_sql,
        result_json=result_json,
        latency_ms=latency_ms,
        tokens=tokens,
        success=success,
        error=error,
        session_id=session_id
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row.id


async def get_session_history(session: AsyncSession, session_id: str, limit: int = 5):
    """Retrieve recent Q&A pairs for context."""
    if not session_id:
        return []
    
    stmt = (
        select(ChatLog)
        .where(ChatLog.session_id == session_id, ChatLog.success == True)
        .order_by(ChatLog.timestamp.desc())
        .limit(limit)
    )
    res = await session.execute(stmt)
    logs = res.scalars().all()
    # Return chronologically (oldest to newest for LLM context)
    return reversed(logs)


async def record_feedback(session: AsyncSession, log_id: int, value: int) -> None:
    await session.execute(
        update(ChatLog).where(ChatLog.id == log_id).values(feedback=value)
    )
    await session.flush()


async def summary(session: AsyncSession) -> dict:
    window = datetime.utcnow() - timedelta(days=30)
    q = (
        select(
            func.count(ChatLog.id).label("total"),
            func.coalesce(func.avg(case((ChatLog.success.is_(True), 1.0), else_=0.0)), 0).label("success_rate"),
            func.coalesce(func.avg(ChatLog.latency_ms), 0).label("avg_latency"),
            func.sum(case((ChatLog.success.is_(False), 1), else_=0)).label("failed"),
            func.sum(case((ChatLog.feedback == 1, 1), else_=0)).label("up"),
            func.sum(case((ChatLog.feedback == -1, 1), else_=0)).label("down"),
        )
        .where(ChatLog.timestamp >= window)
    )
    row = (await session.execute(q)).first() or (0, 0, 0, 0, 0, 0)
    total, success_rate, avg_lat, failed, up, down = row
    fb_total = int((up or 0) + (down or 0))
    fb_ratio = (up or 0) / fb_total if fb_total else 0.0
    return {
        "total_queries": int(total or 0),
        "success_rate": float(success_rate or 0.0),
        "avg_latency_ms": float(avg_lat or 0.0),
        "failed_queries": int(failed or 0),
        "feedback_ratio": float(fb_ratio),
    }


async def recent_failed(session: AsyncSession, limit: int = 20) -> list:
    rows = (
        await session.execute(
            select(ChatLog)
            .where(ChatLog.success.is_(False))
            .order_by(ChatLog.timestamp.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp.isoformat(),
            "question": r.question,
            "error": r.error,
        }
        for r in rows
    ]
