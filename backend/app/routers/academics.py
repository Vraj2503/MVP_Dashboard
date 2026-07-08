from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from typing import Optional

from ..db import get_db
from ..models import Course, ClassGroup, Teacher, Student, StudentSummary, Fee, FeeStatus, Assessment
from ..schemas import (
    CourseOut, CourseCreate, 
    ClassGroupOut, ClassGroupCreate, 
    TeacherOut, TeacherCreate, 
    PaginatedResponse,
    AcademicStudentOut, StudentAssessmentOut, AssessmentCreate, AssessmentUpdate
)

router = APIRouter()

# --- Courses ---------------------------------------------------------------

@router.get("/courses", response_model=PaginatedResponse[CourseOut])
async def list_courses(
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    offset = (page - 1) * limit
    
    q = select(Course)
    if search:
        q = q.where(or_(
            Course.name.ilike(f"%{search}%"),
            Course.code.ilike(f"%{search}%")
        ))
        
    total_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(total_q)).scalar() or 0
    
    q = q.order_by(Course.code).offset(offset).limit(limit)
    items = (await db.execute(q)).scalars().all()
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }

@router.post("/courses", response_model=CourseOut)
async def create_course(course: CourseCreate, db: AsyncSession = Depends(get_db)):
    new_course = Course(**course.model_dump())
    db.add(new_course)
    await db.commit()
    await db.refresh(new_course)
    return new_course

@router.put("/courses/{course_id}", response_model=CourseOut)
async def update_course(course_id: int, course: CourseCreate, db: AsyncSession = Depends(get_db)):
    db_course = await db.get(Course, course_id)
    if not db_course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    for key, value in course.model_dump().items():
        setattr(db_course, key, value)
    
    await db.commit()
    await db.refresh(db_course)
    return db_course

@router.delete("/courses/{course_id}")
async def delete_course(course_id: int, db: AsyncSession = Depends(get_db)):
    db_course = await db.get(Course, course_id)
    if not db_course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    await db.delete(db_course)
    await db.commit()
    return {"message": "Course deleted"}


# --- Classes ---------------------------------------------------------------

@router.get("/classes", response_model=PaginatedResponse[ClassGroupOut])
async def list_classes(
    search: Optional[str] = None,
    grade: Optional[int] = None,
    section: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    offset = (page - 1) * limit
    
    q = select(ClassGroup).options(selectinload(ClassGroup.teacher))
    
    if search:
        q = q.where(ClassGroup.name.ilike(f"%{search}%"))
    if grade is not None:
        q = q.where(ClassGroup.grade == grade)
    if section:
        q = q.where(ClassGroup.section == section)
        
    total_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(total_q)).scalar() or 0
    
    q = q.order_by(ClassGroup.grade, ClassGroup.section).offset(offset).limit(limit)
    items = (await db.execute(q)).scalars().all()
    
    out_items = []
    for item in items:
        out = ClassGroupOut.model_validate(item)
        if item.teacher:
            out.teacher_name = item.teacher.name
        out_items.append(out)
    
    return {
        "items": out_items,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }

@router.post("/classes", response_model=ClassGroupOut)
async def create_class(cg: ClassGroupCreate, db: AsyncSession = Depends(get_db)):
    new_cg = ClassGroup(**cg.model_dump())
    db.add(new_cg)
    await db.commit()
    await db.refresh(new_cg)
    
    q = select(ClassGroup).options(selectinload(ClassGroup.teacher)).where(ClassGroup.id == new_cg.id)
    new_cg = (await db.execute(q)).scalar_one()
    
    out = ClassGroupOut.model_validate(new_cg)
    if new_cg.teacher:
        out.teacher_name = new_cg.teacher.name
    return out

@router.put("/classes/{class_id}", response_model=ClassGroupOut)
async def update_class(class_id: int, cg: ClassGroupCreate, db: AsyncSession = Depends(get_db)):
    db_cg = await db.get(ClassGroup, class_id)
    if not db_cg:
        raise HTTPException(status_code=404, detail="Class not found")
    
    for key, value in cg.model_dump().items():
        setattr(db_cg, key, value)
    
    await db.commit()
    
    q = select(ClassGroup).options(selectinload(ClassGroup.teacher)).where(ClassGroup.id == class_id)
    db_cg = (await db.execute(q)).scalar_one()
    
    out = ClassGroupOut.model_validate(db_cg)
    if db_cg.teacher:
        out.teacher_name = db_cg.teacher.name
    return out

@router.delete("/classes/{class_id}")
async def delete_class(class_id: int, db: AsyncSession = Depends(get_db)):
    db_cg = await db.get(ClassGroup, class_id)
    if not db_cg:
        raise HTTPException(status_code=404, detail="Class not found")
    
    await db.delete(db_cg)
    await db.commit()
    return {"message": "Class deleted"}


# --- Teachers --------------------------------------------------------------

@router.get("/teachers", response_model=PaginatedResponse[TeacherOut])
async def list_teachers(
    search: Optional[str] = None,
    subject: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    offset = (page - 1) * limit
    
    q = select(Teacher)
    if search:
        q = q.where(Teacher.name.ilike(f"%{search}%"))
    if subject:
        q = q.where(Teacher.subject == subject)
        
    total_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(total_q)).scalar() or 0
    
    q = q.order_by(Teacher.name).offset(offset).limit(limit)
    items = (await db.execute(q)).scalars().all()
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }

@router.post("/teachers", response_model=TeacherOut)
async def create_teacher(teacher: TeacherCreate, db: AsyncSession = Depends(get_db)):
    new_teacher = Teacher(**teacher.model_dump())
    db.add(new_teacher)
    await db.commit()
    await db.refresh(new_teacher)
    return new_teacher

@router.put("/teachers/{teacher_id}", response_model=TeacherOut)
async def update_teacher(teacher_id: int, teacher: TeacherCreate, db: AsyncSession = Depends(get_db)):
    db_teacher = await db.get(Teacher, teacher_id)
    if not db_teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    
    for key, value in teacher.model_dump().items():
        setattr(db_teacher, key, value)
    
    await db.commit()
    await db.refresh(db_teacher)
    return db_teacher

@router.delete("/teachers/{teacher_id}")
async def delete_teacher(teacher_id: int, db: AsyncSession = Depends(get_db)):
    db_teacher = await db.get(Teacher, teacher_id)
    if not db_teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    
    await db.delete(db_teacher)
    await db.commit()
    return {"message": "Teacher deleted"}

# --- Students (Academics View) ---------------------------------------------

@router.get("/students", response_model=PaginatedResponse[AcademicStudentOut])
async def list_academic_students(
    search: Optional[str] = None,
    grade: Optional[int] = None,
    section: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    offset = (page - 1) * limit
    
    # We want: Student info, attendance_rate and grade_avg (from Summary), and overdue fees (from Fee)
    
    # Subquery for overdue fees count
    fee_sub = select(
        Fee.student_id,
        func.count(Fee.id).label("overdue_fees")
    ).where(
        Fee.status.in_([FeeStatus.OVERDUE, FeeStatus.UNPAID])
    ).group_by(Fee.student_id).subquery()
    
    q = select(
        Student.id,
        Student.name,
        Student.grade,
        Student.section,
        StudentSummary.attendance_rate,
        StudentSummary.grade_avg,
        func.coalesce(fee_sub.c.overdue_fees, 0).label("overdue_fees")
    ).outerjoin(
        StudentSummary, Student.id == StudentSummary.student_id
    ).outerjoin(
        fee_sub, Student.id == fee_sub.c.student_id
    )
    
    if search:
        q = q.where(Student.name.ilike(f"%{search}%"))
    if grade is not None:
        q = q.where(Student.grade == grade)
    if section:
        q = q.where(Student.section == section)
        
    total_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(total_q)).scalar() or 0
    
    q = q.order_by(Student.name).offset(offset).limit(limit)
    rows = (await db.execute(q)).all()
    
    items = []
    for r in rows:
        items.append(AcademicStudentOut(
            id=r.id,
            name=r.name,
            grade=r.grade,
            section=r.section,
            attendance_rate=r.attendance_rate,
            grade_avg=r.grade_avg,
            overdue_fees=r.overdue_fees
        ))
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }

@router.get("/students/{student_id}/assessments", response_model=list[StudentAssessmentOut])
async def get_student_assessments(student_id: int, db: AsyncSession = Depends(get_db)):
    q = select(Assessment).where(
        Assessment.student_id == student_id
    ).order_by(Assessment.date.desc())
    
    assessments = (await db.execute(q)).scalars().all()
    return assessments

async def _recompute_student_grade_avg(student_id: int, db: AsyncSession):
    q = select(Assessment).where(Assessment.student_id == student_id)
    assessments = (await db.execute(q)).scalars().all()
    
    if assessments:
        total_percent = sum(a.score / a.max_score for a in assessments if a.max_score > 0)
        avg = (total_percent / len(assessments)) * 100
    else:
        avg = 0.0
        
    summary = await db.get(StudentSummary, student_id)
    if summary:
        summary.grade_avg = avg
        db.add(summary)

@router.post("/students/{student_id}/assessments", response_model=StudentAssessmentOut)
async def create_student_assessment(student_id: int, assessment: AssessmentCreate, db: AsyncSession = Depends(get_db)):
    new_assessment = Assessment(**assessment.model_dump(), student_id=student_id)
    db.add(new_assessment)
    await db.commit()
    await db.refresh(new_assessment)
    
    await _recompute_student_grade_avg(student_id, db)
    await db.commit()
    
    return new_assessment

@router.put("/assessments/{assessment_id}", response_model=StudentAssessmentOut)
async def update_assessment(assessment_id: int, assessment: AssessmentUpdate, db: AsyncSession = Depends(get_db)):
    db_assessment = await db.get(Assessment, assessment_id)
    if not db_assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    for key, value in assessment.model_dump(exclude_unset=True).items():
        setattr(db_assessment, key, value)
        
    await db.commit()
    await db.refresh(db_assessment)
    
    await _recompute_student_grade_avg(db_assessment.student_id, db)
    await db.commit()
    
    return db_assessment

@router.delete("/assessments/{assessment_id}")
async def delete_assessment(assessment_id: int, db: AsyncSession = Depends(get_db)):
    db_assessment = await db.get(Assessment, assessment_id)
    if not db_assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    student_id = db_assessment.student_id
    await db.delete(db_assessment)
    await db.commit()
    
    await _recompute_student_grade_avg(student_id, db)
    await db.commit()
    
    return {"message": "Assessment deleted"}

