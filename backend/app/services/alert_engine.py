"""Automated alert generation engine.

Scans student_summary data against configurable thresholds and creates
Alert rows for conditions that need admin attention. Designed to be run
periodically by the scheduler.

Alert rules implemented:
1. Attendance Drop  — students below a threshold attendance rate
2. Risk Escalation  — students who moved from Watch → At-Risk
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List

from sqlalchemy import select, func, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Alert, AlertSeverity, AlertStatus, StudentSummary, Student, RiskTier

logger = logging.getLogger("alert_engine")

# Configurable thresholds
ATTENDANCE_THRESHOLD = 0.75  # 75%


async def _has_recent_alert(session: AsyncSession, alert_type: str, hours: int = 24) -> bool:
    """Check if an open alert of the same type exists from the last N hours."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    q = select(func.count(Alert.id)).where(
        Alert.type == alert_type,
        Alert.status == AlertStatus.OPEN,
        Alert.created_at >= cutoff,
    )
    count = (await session.execute(q)).scalar() or 0
    return count > 0


async def check_attendance_drops(session: AsyncSession) -> List[Alert]:
    """Find students below the attendance threshold and generate alerts."""
    if await _has_recent_alert(session, "attendance_drop"):
        logger.info("Skipping attendance_drop: recent alert exists.")
        return []

    # Count students below threshold, grouped by grade
    q = (
        select(
            Student.grade,
            func.count(StudentSummary.student_id).label("cnt"),
        )
        .join(Student, Student.id == StudentSummary.student_id)
        .where(StudentSummary.attendance_rate < ATTENDANCE_THRESHOLD)
        .group_by(Student.grade)
        .order_by(func.count(StudentSummary.student_id).desc())
    )
    rows = (await session.execute(q)).all()

    if not rows:
        return []

    total_affected = sum(r.cnt for r in rows)
    worst_grades = rows[:3]  # top 3 worst grades

    # Determine severity
    if total_affected > 20:
        severity = AlertSeverity.CRITICAL
    elif total_affected > 10:
        severity = AlertSeverity.HIGH
    elif total_affected > 5:
        severity = AlertSeverity.MEDIUM
    else:
        severity = AlertSeverity.LOW

    grade_detail = ", ".join(f"Grade {r.grade} ({r.cnt})" for r in worst_grades)
    message = (
        f"{total_affected} students have dropped below {ATTENDANCE_THRESHOLD * 100:.0f}% attendance. "
        f"Most affected: {grade_detail}."
    )
    suggested_action = (
        f"Schedule parent-teacher meetings for affected students, "
        f"prioritising Grade {worst_grades[0].grade} with {worst_grades[0].cnt} students."
    )

    alert = Alert(
        type="attendance_drop",
        student_id=None,
        severity=severity,
        message=message,
        suggested_action=suggested_action,
        status=AlertStatus.OPEN,
    )
    session.add(alert)
    await session.flush()
    logger.info("Created attendance_drop alert: %d students affected", total_affected)
    return [alert]


async def check_risk_escalations(session: AsyncSession) -> List[Alert]:
    """Find students who escalated from Watch → At-Risk."""
    if await _has_recent_alert(session, "risk_escalation"):
        logger.info("Skipping risk_escalation: recent alert exists.")
        return []

    # Find students whose current tier is At-Risk but previous was Watch
    q = (
        select(
            func.count(StudentSummary.student_id).label("cnt"),
        )
        .where(
            StudentSummary.risk_tier == RiskTier.AT_RISK,
            StudentSummary.previous_risk_tier == RiskTier.WATCH,
        )
    )
    count = (await session.execute(q)).scalar() or 0

    if count == 0:
        return []

    severity = AlertSeverity.HIGH if count > 5 else AlertSeverity.MEDIUM

    message = (
        f"{count} students have escalated from Watch to At-Risk tier since the last assessment."
    )
    suggested_action = (
        f"Review intervention plans for these {count} newly at-risk students. "
        f"Consider scheduling counselling sessions and notifying parents."
    )

    alert = Alert(
        type="risk_escalation",
        student_id=None,
        severity=severity,
        message=message,
        suggested_action=suggested_action,
        status=AlertStatus.OPEN,
    )
    session.add(alert)
    await session.flush()
    logger.info("Created risk_escalation alert: %d students escalated", count)
    return [alert]


async def run_all_checks(session: AsyncSession) -> List[Alert]:
    """Run all alert checks and return created alerts."""
    alerts: List[Alert] = []
    alerts.extend(await check_attendance_drops(session))
    alerts.extend(await check_risk_escalations(session))
    await session.commit()
    logger.info("Alert scan complete: %d alerts created.", len(alerts))
    return alerts
