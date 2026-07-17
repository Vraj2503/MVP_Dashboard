from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, func, case
import datetime
import time
import logging

logger = logging.getLogger("attendance")

from typing import List, Optional

from ..db import get_db, AppSessionLocal
from ..models import Student, Attendance, StudentSummary
from ..schemas import AttendanceClassView, AttendanceBulkCreate, AttendanceOut, StudentCalendarDay, ClassCalendarDay
import calendar

async def recompute_attendance_rates_bg(student_ids: List[int]):
    """Background task: recompute attendance rates with its own DB session."""
    if not student_ids:
        return
    t0 = time.monotonic()
    async with AppSessionLocal() as db:
        att_stats_q = select(
            Attendance.student_id,
            func.sum(case((Attendance.status.in_(["Present", "Absent", "Late"]), 1), else_=0)).label("total_days"),
            func.sum(case((Attendance.status == "Present", 1), else_=0)).label("present_days")
        ).where(Attendance.student_id.in_(student_ids)).group_by(Attendance.student_id)
        
        stats_records = (await db.execute(att_stats_q)).all()
        t1 = time.monotonic()
        logger.info("[recompute] SELECT stats took %.2fs", t1 - t0)
        
        rate_map = {}
        for r in stats_records:
            if r.total_days > 0:
                rate_map[r.student_id] = float(r.present_days or 0) / float(r.total_days)
            else:
                rate_map[r.student_id] = 0.0
                
        # Bulk fetch existing summaries
        summary_q = select(StudentSummary).where(StudentSummary.student_id.in_(student_ids))
        existing_summaries = (await db.execute(summary_q)).scalars().all()
        summary_map = {s.student_id: s for s in existing_summaries}
        t2 = time.monotonic()
        logger.info("[recompute] SELECT summaries took %.2fs", t2 - t1)
        
        update_summaries = []
        new_summaries = []
        for sid in student_ids:
            summary = summary_map.get(sid)
            if summary:
                update_summaries.append({
                    "student_id": sid,
                    "attendance_rate": rate_map.get(sid, 0.0),
                    "updated_at": datetime.datetime.utcnow()
                })
            else:
                new_summaries.append(StudentSummary(
                    student_id=sid,
                    attendance_rate=rate_map.get(sid, 0.0),
                    risk_tier="Safe",
                    updated_at=datetime.datetime.utcnow()
                ))
        
        if update_summaries:
            await db.execute(update(StudentSummary), update_summaries)
        if new_summaries:
            db.add_all(new_summaries)
                
        await db.commit()
        t3 = time.monotonic()
        logger.info("[recompute] COMMIT took %.2fs | total=%.2fs", t3 - t2, t3 - t0)

router = APIRouter()

@router.get("/class", response_model=List[AttendanceClassView])
async def get_class_attendance(
    grade: int,
    section: str,
    date: datetime.date,
    db: AsyncSession = Depends(get_db)
):
    # Fetch all students for the given class
    student_q = select(Student).where(and_(Student.grade == grade, Student.section == section)).order_by(Student.name)
    students = (await db.execute(student_q)).scalars().all()
    
    if not students:
        return []
        
    student_ids = [s.id for s in students]
    
    # Fetch attendance records for these students on the given date
    att_q = select(Attendance).where(
        and_(
            Attendance.student_id.in_(student_ids),
            Attendance.date == date
        )
    )
    records = (await db.execute(att_q)).scalars().all()
    att_map = {r.student_id: r.status for r in records}
    
    out = []
    for s in students:
        out.append(AttendanceClassView(
            student_id=s.id,
            student_name=s.name,
            status=att_map.get(s.id)
        ))
        
    return out

@router.post("/bulk", response_model=dict)
async def bulk_upsert_attendance(
    data: AttendanceBulkCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    t_start = time.monotonic()
    student_ids = [r.student_id for r in data.records]
    if not student_ids:
        return {"message": "No records to update"}
        
    # Step 1: DELETE existing records for these students on this date
    delete_stmt = text(
        "DELETE FROM attendance WHERE student_id IN :sids AND date = :dt"
    ).bindparams(bindparam("sids", expanding=True), bindparam("dt"))
    await db.execute(delete_stmt, {"sids": student_ids, "dt": data.date})
    
    # Step 2: Batch INSERT all records in one statement
    if data.records:
        values = [
            {"sid": r.student_id, "dt": data.date, "st": r.status, "pd": r.period}
            for r in data.records
        ]
        insert_stmt = text(
            "INSERT INTO attendance (student_id, date, status, period) "
            "VALUES (:sid, :dt, :st, :pd)"
        )
        await db.execute(insert_stmt, values)
        
    # Step 3: Commit
    await db.commit()
    t_commit = time.monotonic()
    logger.info("[bulk] raw SQL total=%.2fs", t_commit - t_start)
    
    # Background: recompute attendance rates (non-blocking)
    background_tasks.add_task(recompute_attendance_rates_bg, student_ids)
    return {"message": f"Successfully updated attendance for {len(data.records)} students"}

@router.put("/{attendance_id}", response_model=AttendanceOut)
async def update_attendance(attendance_id: int, status: str, db: AsyncSession = Depends(get_db)):
    att = await db.get(Attendance, attendance_id)
    if not att:
        raise HTTPException(status_code=404, detail="Attendance record not found")
        
    att.status = status
    await db.commit()
    await db.refresh(att)
    await recompute_attendance_rates(db, [att.student_id])
    return att

@router.delete("/{attendance_id}")
async def delete_attendance(attendance_id: int, db: AsyncSession = Depends(get_db)):
    att = await db.get(Attendance, attendance_id)
    if not att:
        raise HTTPException(status_code=404, detail="Attendance record not found")
        
    student_id = att.student_id
    await db.delete(att)
    await db.commit()
    await recompute_attendance_rates(db, [student_id])
    return {"message": "Attendance record deleted"}

@router.get("/student-calendar", response_model=List[StudentCalendarDay])
async def get_student_calendar(
    student_id: int,
    year: int,
    month: int,
    db: AsyncSession = Depends(get_db)
):
    start_date = datetime.date(year, month, 1)
    end_date = datetime.date(year, month, calendar.monthrange(year, month)[1])
    
    q = select(Attendance).where(
        and_(
            Attendance.student_id == student_id,
            Attendance.date >= start_date,
            Attendance.date <= end_date
        )
    ).order_by(Attendance.date)
    records = (await db.execute(q)).scalars().all()
    
    return [
        StudentCalendarDay(date=r.date, status=r.status)
        for r in records
    ]

@router.get("/class-calendar", response_model=List[ClassCalendarDay])
async def get_class_calendar(
    grade: int,
    section: str,
    year: int,
    month: int,
    db: AsyncSession = Depends(get_db)
):
    start_date = datetime.date(year, month, 1)
    end_date = datetime.date(year, month, calendar.monthrange(year, month)[1])
    
    # get students in class
    student_q = select(Student.id).where(
        and_(Student.grade == grade, Student.section == section)
    )
    student_ids = (await db.execute(student_q)).scalars().all()
    if not student_ids:
        return []
        
    q = select(
        Attendance.date,
        func.count(Attendance.id).label("total"),
        func.sum(case((Attendance.status == 'Present', 1), else_=0)).label("present"),
        func.sum(case((Attendance.status == 'Holiday', 1), else_=0)).label("holiday")
    ).where(
        and_(
            Attendance.student_id.in_(student_ids),
            Attendance.date >= start_date,
            Attendance.date <= end_date
        )
    ).group_by(Attendance.date).order_by(Attendance.date)
    
    records = (await db.execute(q)).all()
    
    out = []
    for r in records:
        total = int(r.total)
        present = int(r.present or 0)
        holiday_count = int(r.holiday or 0)
        
        is_holiday = (holiday_count == total and total > 0)
        
        # If it's a holiday, we can say percentage is 0 but it won't matter visually
        percentage = (present / total * 100) if total > 0 and not is_holiday else 0.0
        
        out.append(ClassCalendarDay(
            date=r.date,
            total=total,
            present=present,
            percentage=round(percentage, 1),
            is_holiday=is_holiday
        ))
    return out
