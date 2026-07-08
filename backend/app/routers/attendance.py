from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, func, case
import datetime

from typing import List, Optional

from ..db import get_db
from ..models import Student, Attendance, StudentSummary
from ..schemas import AttendanceClassView, AttendanceBulkCreate, AttendanceOut

async def recompute_attendance_rates(db: AsyncSession, student_ids: List[int]):
    if not student_ids:
        return
        
    att_stats_q = select(
        Attendance.student_id,
        func.count(Attendance.id).label("total_days"),
        func.sum(case((Attendance.status == "Present", 1), else_=0)).label("present_days")
    ).where(Attendance.student_id.in_(student_ids)).group_by(Attendance.student_id)
    
    stats_records = (await db.execute(att_stats_q)).all()
    
    rate_map = {}
    for r in stats_records:
        if r.total_days > 0:
            rate_map[r.student_id] = float(r.present_days or 0) / float(r.total_days)
        else:
            rate_map[r.student_id] = 0.0
            
    for sid in student_ids:
        summary = await db.get(StudentSummary, sid)
        if summary:
            summary.attendance_rate = rate_map.get(sid, 0.0)
            summary.updated_at = datetime.datetime.utcnow()
        else:
            new_summary = StudentSummary(
                student_id=sid,
                attendance_rate=rate_map.get(sid, 0.0),
                updated_at=datetime.datetime.utcnow()
            )
            db.add(new_summary)
            
    await db.commit()

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
async def bulk_upsert_attendance(data: AttendanceBulkCreate, db: AsyncSession = Depends(get_db)):
    # First, get existing records for this date and class
    # We can just fetch by student_ids in the payload
    student_ids = [r.student_id for r in data.records]
    if not student_ids:
        return {"message": "No records to update"}
        
    att_q = select(Attendance).where(
        and_(
            Attendance.student_id.in_(student_ids),
            Attendance.date == data.date
        )
    )
    existing_records = (await db.execute(att_q)).scalars().all()
    existing_map = {r.student_id: r for r in existing_records}
    
    for req_rec in data.records:
        if req_rec.student_id in existing_map:
            # Update existing
            existing = existing_map[req_rec.student_id]
            existing.status = req_rec.status
            if req_rec.period is not None:
                existing.period = req_rec.period
        else:
            # Create new
            new_att = Attendance(
                student_id=req_rec.student_id,
                date=data.date,
                status=req_rec.status,
                period=req_rec.period
            )
            db.add(new_att)
            
    await db.commit()
    await recompute_attendance_rates(db, student_ids)
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
