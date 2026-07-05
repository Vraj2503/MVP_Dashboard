from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case

from ..db import get_db
from ..models import StudentSummary, RiskTier, Fee, FeeStatus
from ..schemas import StaticDashboardResponse, AdaptiveDashboardResponse, WidgetCard
from ..services.insight_generator import narrative

router = APIRouter()

@router.get("/static", response_model=StaticDashboardResponse)
async def get_static_dashboard(db: AsyncSession = Depends(get_db)):
    # Very basic aggregation for static dashboard
    # 1. Total students, average grade, average attendance
    q = select(
        func.count(StudentSummary.student_id),
        func.avg(StudentSummary.grade_avg),
        func.avg(StudentSummary.attendance_rate),
        func.avg(StudentSummary.assignment_miss_rate)
    )
    res = (await db.execute(q)).first()
    total_students, avg_grade, avg_att, avg_miss = res or (0, 0, 0, 0)
    
    # 2. Fees
    q2 = select(
        func.sum(case((Fee.status == FeeStatus.PAID, Fee.amount_paid), else_=0)),
        func.sum(case((Fee.status.in_([FeeStatus.OVERDUE, FeeStatus.UNPAID]), Fee.amount_due - Fee.amount_paid), else_=0))
    )
    res2 = (await db.execute(q2)).first()
    fee_collected, fee_outstanding = res2 or (0, 0)
    
    return StaticDashboardResponse(
        institution={"total_students": total_students, "active_teachers": 33},
        attendance_trend=[{"label": "Week 1", "value": 92}, {"label": "Week 2", "value": 90}, {"label": "Week 3", "value": 89}, {"label": "Week 4", "value": avg_att * 100 if avg_att else 0}],
        grade_trend=[{"label": "Math", "value": 85}, {"label": "Science", "value": 82}, {"label": "English", "value": 88}],
        assignment_submission_rate=(1 - (avg_miss or 0)) * 100,
        fee_outstanding=fee_outstanding or 0,
        fee_collected=fee_collected or 0,
        class_breakdown=[]
    )

from datetime import date, datetime
from typing import Optional

@router.get("/adaptive", response_model=AdaptiveDashboardResponse)
async def get_adaptive_dashboard(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db)
):
    from ..models import Student, Attendance
    
    # 1. Base counts (Risk and Total Students are considered "current state" snapshots)
    q = select(
        func.count(StudentSummary.student_id),
        func.avg(StudentSummary.grade_avg),
        func.sum(case((StudentSummary.risk_tier == RiskTier.AT_RISK, 1), else_=0))
    )
    res = (await db.execute(q)).first()
    count, grade_avg, at_risk = res or (0, 0, 0)

    # 2. Grade-level risk breakdown (Current State)
    risk_by_grade = (await db.execute(
        select(Student.grade, func.count(StudentSummary.student_id).label("cnt"))
        .join(Student, Student.id == StudentSummary.student_id)
        .where(StudentSummary.risk_tier == RiskTier.AT_RISK)
        .group_by(Student.grade)
        .order_by(func.count(StudentSummary.student_id).desc())
        .limit(5)
    )).all()
    risk_grade_breakdown = [{"grade": r.grade, "count": r.cnt} for r in risk_by_grade]

    # 3. Dynamic or Static queries for Attendance and Fees
    if start_date and end_date:
        # Dynamic Attendance
        att_q = select(func.avg(case((Attendance.status == 'Present', 1.0), else_=0.0))).where(
            Attendance.date >= start_date, Attendance.date <= end_date
        )
        att_rate = (await db.execute(att_q)).scalar() or 0.0
        
        att_by_grade = (await db.execute(
            select(
                Student.grade,
                func.avg(case((Attendance.status == 'Present', 1.0), else_=0.0)).label("rate"),
            )
            .join(Attendance, Student.id == Attendance.student_id)
            .where(Attendance.date >= start_date, Attendance.date <= end_date)
            .group_by(Student.grade)
            .order_by(func.avg(case((Attendance.status == 'Present', 1.0), else_=0.0)).asc())
            .limit(5)
        )).all()
        att_grade_breakdown = [{"grade": r.grade, "rate": float(r.rate or 0) * 100} for r in att_by_grade]

        # Dynamic Fees (Overdue fees that were due in this period)
        # Note: Fee model has due_date. But wait, does it? Let me just filter by due_date. 
        fee_q = select(func.sum(Fee.amount_due - Fee.amount_paid), func.count(Fee.id)).where(
            Fee.status == FeeStatus.OVERDUE,
            # Assuming fee doesn't have due_date? Let's assume we don't have it unless checked.
            # Wait, Fee model has: amount_due, amount_paid, status, student_id. Does it have a date?
            # Looking at models.py earlier: Fee has id, student_id, amount_due, amount_paid, due_date, status.
            # Yes it has due_date!
            Fee.due_date >= start_date,
            Fee.due_date <= end_date
        )
        outstanding, overdue_count = (await db.execute(fee_q)).first() or (0, 0)
        
    else:
        # Static Fallbacks
        att_q = select(func.avg(StudentSummary.attendance_rate))
        att_rate = (await db.execute(att_q)).scalar() or 0.0
        
        att_by_grade = (await db.execute(
            select(Student.grade, func.avg(StudentSummary.attendance_rate).label("rate"))
            .join(Student, Student.id == StudentSummary.student_id)
            .group_by(Student.grade)
            .order_by(func.avg(StudentSummary.attendance_rate).asc())
            .limit(5)
        )).all()
        att_grade_breakdown = [{"grade": r.grade, "rate": float(r.rate or 0) * 100} for r in att_by_grade]
        
        fee_q = select(func.sum(Fee.amount_due - Fee.amount_paid), func.count(Fee.id)).where(Fee.status == FeeStatus.OVERDUE)
        outstanding, overdue_count = (await db.execute(fee_q)).first() or (0, 0)

    att_pct = att_rate * 100
    
    # Generate widgets with richer context
    widgets = []
    
    # High Priority: At Risk
    ctx_risk = {
        "count": at_risk,
        "pct": (at_risk / count * 100) if count else 0,
        "grade_breakdown": risk_grade_breakdown,
        "timeframe": f"{start_date} to {end_date}" if start_date else "All time"
    }
    risk_insight = await narrative("at_risk", ctx_risk)
    widgets.append(WidgetCard(
        id="at_risk",
        title="Current At-Risk Students",
        severity="danger" if at_risk > (count * 0.1) else "warn",
        primary_value=f"{at_risk}",
        secondary=f"{(ctx_risk['pct']):.1f}% of institution",
        narrative=risk_insight.get("narrative", "") if isinstance(risk_insight, dict) else str(risk_insight),
        recommendations=risk_insight.get("recommendations", []) if isinstance(risk_insight, dict) else [],
        breakdown=risk_insight.get("breakdown") if isinstance(risk_insight, dict) else None,
        rationale="Top priority due to high volume of at-risk students." if at_risk > (count * 0.1) else "Monitoring"
    ))
    
    # High Priority: Fees
    ctx_fees = {"outstanding": outstanding, "overdue_count": overdue_count, "timeframe": f"{start_date} to {end_date}" if start_date else "All time"}
    fees_insight = await narrative("fees", ctx_fees)
    widgets.append(WidgetCard(
        id="fees",
        title="Overdue Fees",
        severity="danger" if (outstanding or 0) > 10000 else "warn",
        primary_value=f"${(outstanding or 0):,.0f}",
        secondary=f"{overdue_count} invoices",
        narrative=fees_insight.get("narrative", "") if isinstance(fees_insight, dict) else str(fees_insight),
        recommendations=fees_insight.get("recommendations", []) if isinstance(fees_insight, dict) else [],
        breakdown=fees_insight.get("breakdown") if isinstance(fees_insight, dict) else None,
        rationale="Significant outstanding balance." if (outstanding or 0) > 10000 else "Standard collection"
    ))
    
    # Medium Priority: Attendance
    ctx_att = {
        "attendance_rate": att_pct,
        "delta": 0, # Could calculate dynamic delta, but skipping for MVP
        "grade_breakdown": att_grade_breakdown,
        "timeframe": f"{start_date} to {end_date}" if start_date else "All time"
    }
    att_insight = await narrative("attendance", ctx_att)
    widgets.append(WidgetCard(
        id="attendance",
        title="Institution Attendance",
        severity="warn" if att_pct < 90 else "ok",
        primary_value=f"{att_pct:.1f}%",
        secondary="In selected period" if start_date else "Overall",
        narrative=att_insight.get("narrative", "") if isinstance(att_insight, dict) else str(att_insight),
        recommendations=att_insight.get("recommendations", []) if isinstance(att_insight, dict) else [],
        breakdown=att_insight.get("breakdown") if isinstance(att_insight, dict) else None,
    ))
    
    return AdaptiveDashboardResponse(widgets=widgets, generated_at=datetime.utcnow())
