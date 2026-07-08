from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, text
from sqlalchemy.orm import selectinload

from typing import Optional

from ..db import get_db
from ..models import (
    Student, StudentSummary, Assessment, RiskTier,
    Attendance, Assignment, Fee, FeeInvoice, Payment, BehaviorNote, Alert
)
from ..schemas import (
    StudentOut, StudentCreate, StudentDetail, PaginatedResponse, SubjectGrade
)

router = APIRouter()

@router.get("/", response_model=PaginatedResponse[StudentOut])
async def list_students(
    search: Optional[str] = None,
    grade: Optional[int] = None,
    section: Optional[str] = None,
    gender: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    offset = (page - 1) * limit
    
    q = select(Student, StudentSummary).outerjoin(StudentSummary, Student.id == StudentSummary.student_id)
    
    if search:
        q = q.where(Student.name.ilike(f"%{search}%"))
    if grade is not None:
        q = q.where(Student.grade == grade)
    if section:
        q = q.where(Student.section == section)
    if gender:
        q = q.where(Student.gender == gender)
        
    total_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(total_q)).scalar() or 0
    
    q = q.order_by(Student.name).offset(offset).limit(limit)
    results = (await db.execute(q)).all()
    
    items = []
    for student, summary in results:
        out = StudentOut.model_validate(student)
        if summary:
            out.attendance_rate = summary.attendance_rate
            out.grade_avg = summary.grade_avg
        items.append(out)
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }

@router.get("/{student_id}/details", response_model=StudentDetail)
async def get_student_details(student_id: int, db: AsyncSession = Depends(get_db)):
    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    summary = await db.get(StudentSummary, student_id)
    
    out = StudentDetail.model_validate(student)
    if summary:
        out.attendance_rate = summary.attendance_rate
        out.grade_avg = summary.grade_avg
        
    # Get per-subject grades
    q = select(
        Assessment.subject, 
        func.avg(Assessment.score).label("average_score"),
        func.count(Assessment.id).label("assessment_count")
    ).where(Assessment.student_id == student_id).group_by(Assessment.subject)
    
    assessments = (await db.execute(q)).all()
    out.grades = [{"subject": a.subject, "average_score": float(a.average_score or 0.0), "assessment_count": a.assessment_count} for a in assessments]
    
    return out

@router.post("/", response_model=StudentOut)
async def create_student(student: StudentCreate, db: AsyncSession = Depends(get_db)):
    new_student = Student(**student.model_dump())
    db.add(new_student)
    await db.commit()
    await db.refresh(new_student)
    
    # Create a default summary record so the student appears in dashboard counts
    new_summary = StudentSummary(
        student_id=new_student.id,
        risk_tier=RiskTier.SAFE,
        previous_risk_tier=RiskTier.SAFE
    )
    db.add(new_summary)
    await db.commit()
    
    return new_student

@router.put("/{student_id}", response_model=StudentOut)
async def update_student(student_id: int, student: StudentCreate, db: AsyncSession = Depends(get_db)):
    db_student = await db.get(Student, student_id)
    if not db_student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    for key, value in student.model_dump().items():
        setattr(db_student, key, value)
    
    await db.commit()
    await db.refresh(db_student)
    
    summary = await db.get(StudentSummary, student_id)
    out = StudentOut.model_validate(db_student)
    if summary:
        out.attendance_rate = summary.attendance_rate
        out.grade_avg = summary.grade_avg
        
    return out

@router.delete("/{student_id}")
async def delete_student(student_id: int, db: AsyncSession = Depends(get_db)):
    db_student = await db.get(Student, student_id)
    if not db_student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Manually delete all child records to satisfy foreign key constraints
    await db.execute(delete(StudentSummary).where(StudentSummary.student_id == student_id))
    await db.execute(delete(Attendance).where(Attendance.student_id == student_id))
    await db.execute(delete(Assessment).where(Assessment.student_id == student_id))
    await db.execute(delete(Assignment).where(Assignment.student_id == student_id))
    await db.execute(delete(Fee).where(Fee.student_id == student_id))
    
    # Use text for payments because the ORM model differs from the DB schema and payments reference fee_invoices
    await db.execute(text("DELETE FROM payments WHERE invoice_id IN (SELECT id FROM fee_invoices WHERE student_id = :sid)"), {"sid": student_id})
    
    await db.execute(delete(FeeInvoice).where(FeeInvoice.student_id == student_id))
    await db.execute(delete(BehaviorNote).where(BehaviorNote.student_id == student_id))
    await db.execute(delete(Alert).where(Alert.student_id == student_id))
    
    await db.delete(db_student)
    await db.commit()
    return {"message": "Student deleted"}
