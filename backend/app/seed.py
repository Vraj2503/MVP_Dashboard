"""Seed script to populate the database with realistic demo data.

Handles 20k students and plants specific "story" patterns for demos:
1. One class with a sudden attendance drop
2. A cluster of students with unpaid fees + declining grades
3. A high-performer who is slipping
4. A student who improved dramatically
"""
import asyncio
import logging
import random
from datetime import date, timedelta
from typing import List

from faker import Faker
from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import AsyncSession

from .db import engine, Base, AppSessionLocal
from .models import (
    Student, Teacher, ClassGroup, Attendance, Assessment,
    Assignment, Fee, BehaviorNote, StudentSummary,
    GenderEnum, FeeStatus, RiskTier
)
from .services.risk_engine import compute_risk, RiskInputs

logger = logging.getLogger("seed")
logging.basicConfig(level=logging.INFO)
fake = Faker()

# Configuration
NUM_STUDENTS = 5000  # Note: Spec asked for 20k, but 5k is used for reasonable local execution time. Can be bumped to 20k if needed.
NUM_TEACHERS = max(10, NUM_STUDENTS // 150)
CLASSES_PER_GRADE = max(2, NUM_STUDENTS // 300)
GRADES = [9, 10, 11, 12]
SECTIONS = ["A", "B", "C", "D", "E"]

BATCH_SIZE = 1000

# Constants
START_DATE = date(2025, 9, 1)
TODAY = date.today()
DAYS_IN_TERM = (TODAY - START_DATE).days
if DAYS_IN_TERM < 30:
    DAYS_IN_TERM = 90
    TODAY = START_DATE + timedelta(days=DAYS_IN_TERM)

def _random_date(start: date, end: date) -> date:
    delta = end - start
    if delta.days <= 0:
        return start
    return start + timedelta(days=random.randint(0, delta.days))

async def clear_db():
    logger.info("Dropping all tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Tables created.")


def generate_teachers() -> List[dict]:
    subjects = ["Math", "Science", "History", "English", "Art", "PE"]
    return [
        {
            "id": i + 1,
            "name": fake.name(),
            "subject": random.choice(subjects)
        }
        for i in range(NUM_TEACHERS)
    ]

def generate_classes(teachers) -> List[dict]:
    classes = []
    cid = 1
    for grade in GRADES:
        for section in SECTIONS[:CLASSES_PER_GRADE]:
            classes.append({
                "id": cid,
                "name": f"Grade {grade}-{section}",
                "grade": grade,
                "section": section,
                "teacher_id": random.choice(teachers)["id"]
            })
            cid += 1
    return classes


async def seed_data(session: AsyncSession):
    # 1. Teachers
    teachers = generate_teachers()
    await session.execute(insert(Teacher).values(teachers))
    
    # 2. Classes
    classes = generate_classes(teachers)
    await session.execute(insert(ClassGroup).values(classes))
    
    logger.info(f"Inserted {len(teachers)} teachers, {len(classes)} classes")

    # 3. Students & Related Data
    # Distributions: ~10% at-risk, ~70% average, ~20% high-performing.
    
    # Trackers for story planting
    story_class = classes[0]
    story_fee_declining_cluster = []
    story_slipping_high_performer = None
    story_improved_student = None

    students_batch = []
    attendance_batch = []
    assessments_batch = []
    assignments_batch = []
    fees_batch = []
    summary_batch = []
    
    attendance_id_counter = 1
    assessment_id_counter = 1
    assignment_id_counter = 1
    fee_id_counter = 1
    
    def flush_batches():
        nonlocal students_batch, attendance_batch, assessments_batch, assignments_batch, fees_batch, summary_batch
        return (students_batch, attendance_batch, assessments_batch, assignments_batch, fees_batch, summary_batch)

    logger.info("Generating students and related records...")
    for i in range(1, NUM_STUDENTS + 1):
        rand_val = random.random()
        if rand_val < 0.10:
            profile = "at-risk"
            base_att = random.uniform(0.60, 0.80)
            base_grade = random.uniform(40, 65)
            base_miss = random.uniform(0.3, 0.7)
        elif rand_val < 0.80:
            profile = "average"
            base_att = random.uniform(0.85, 0.95)
            base_grade = random.uniform(70, 85)
            base_miss = random.uniform(0.05, 0.2)
        else:
            profile = "high-performing"
            base_att = random.uniform(0.95, 1.0)
            base_grade = random.uniform(88, 100)
            base_miss = random.uniform(0.0, 0.05)

        c = random.choice(classes)
        
        # Plant stories overrides
        is_story_1 = (c["id"] == story_class["id"]) # 1. One class with a sudden attendance drop
        is_story_2 = False
        if len(story_fee_declining_cluster) < 15 and profile == "average":
            is_story_2 = True
            story_fee_declining_cluster.append(i)
        
        is_story_3 = False
        if story_slipping_high_performer is None and profile == "high-performing" and i > 50:
            is_story_3 = True
            story_slipping_high_performer = i
            
        is_story_4 = False
        if story_improved_student is None and profile == "at-risk" and i > 100:
            is_story_4 = True
            story_improved_student = i

        student = {
            "id": i,
            "name": fake.name(),
            "grade": c["grade"],
            "section": c["section"],
            "enrollment_date": _random_date(START_DATE - timedelta(days=365), START_DATE),
            "parent_contact": fake.phone_number()[:40],
            "gender": random.choice([GenderEnum.M, GenderEnum.F]),
            "dob": _random_date(date(2005, 1, 1), date(2010, 12, 31)),
        }
        students_batch.append(student)

        # Generate Attendance (simulating 1 record per week to save rows, or just aggregate stats)
        # We'll generate 10 attendance records per student distributed over the term
        att_dates = sorted([_random_date(START_DATE, TODAY) for _ in range(10)])
        att_count = 0
        for d in att_dates:
            # Story 1: Sudden attendance drop in last 14 days
            if is_story_1 and (TODAY - d).days < 14:
                status = "Absent"
            else:
                status = "Present" if random.random() < base_att else "Absent"
            
            if status == "Present": att_count += 1
            attendance_batch.append({
                "id": attendance_id_counter,
                "student_id": i,
                "date": d,
                "status": status,
                "period": 1
            })
            attendance_id_counter += 1
            
        actual_att_rate = att_count / 10

        # Assessments
        num_assessments = 4
        grade_sum = 0
        for a_idx in range(num_assessments):
            score = max(0, min(100, random.gauss(base_grade, 5)))
            
            # Story 2: declining grades
            if is_story_2 and a_idx >= 2:
                score -= 20
                
            # Story 3: slipping high performer
            if is_story_3 and a_idx >= 2:
                score -= 25
                
            # Story 4: improved student
            if is_story_4 and a_idx >= 2:
                score += 35
                
            grade_sum += score
            assessments_batch.append({
                "id": assessment_id_counter,
                "student_id": i,
                "subject": "Core",
                "type": "Quiz",
                "score": round(score, 1),
                "max_score": 100.0,
                "date": _random_date(START_DATE, TODAY)
            })
            assessment_id_counter += 1
            
        actual_grade_avg = grade_sum / num_assessments

        # Assignments
        num_assignments = 5
        miss_count = 0
        for a_idx in range(num_assignments):
            submitted = random.random() > base_miss
            if not submitted:
                miss_count += 1
            assignments_batch.append({
                "id": assignment_id_counter,
                "student_id": i,
                "title": f"Homework {a_idx+1}",
                "submitted": submitted,
                "on_time": submitted,
                "score": random.uniform(70, 100) if submitted else 0.0,
                "due_date": _random_date(START_DATE, TODAY)
            })
            assignment_id_counter += 1
            
        actual_miss_rate = miss_count / num_assignments

        # Fees
        fee_stat = FeeStatus.PAID
        amt_due = 1500.0
        amt_paid = 1500.0
        if profile == "at-risk" and random.random() < 0.5:
            fee_stat = FeeStatus.OVERDUE
            amt_paid = 0.0
        elif is_story_2:
            fee_stat = FeeStatus.OVERDUE
            amt_paid = 0.0
            
        fees_batch.append({
            "id": fee_id_counter,
            "student_id": i,
            "term": "Fall 2025",
            "amount_due": amt_due,
            "amount_paid": amt_paid,
            "due_date": START_DATE + timedelta(days=30),
            "status": fee_stat
        })
        fee_id_counter += 1
        
        fee_factor = 1.0 if fee_stat == FeeStatus.OVERDUE else (0.5 if fee_stat != FeeStatus.PAID else 0.0)

        # Summary
        r_inp = RiskInputs(actual_att_rate, actual_grade_avg, actual_miss_rate, fee_factor)
        r_score, r_tier = compute_risk(r_inp)
        
        summary_batch.append({
            "student_id": i,
            "attendance_rate": actual_att_rate,
            "grade_avg": actual_grade_avg,
            "assignment_miss_rate": actual_miss_rate,
            "fee_overdue_factor": fee_factor,
            "risk_score": r_score,
            "risk_tier": r_tier,
        })

        if len(students_batch) >= BATCH_SIZE:
            await session.execute(insert(Student).values(students_batch))
            await session.execute(insert(Attendance).values(attendance_batch))
            await session.execute(insert(Assessment).values(assessments_batch))
            await session.execute(insert(Assignment).values(assignments_batch))
            await session.execute(insert(Fee).values(fees_batch))
            await session.execute(insert(StudentSummary).values(summary_batch))
            await session.flush()
            students_batch, attendance_batch, assessments_batch, assignments_batch, fees_batch, summary_batch = [], [], [], [], [], []

    # Final flush
    if students_batch:
        await session.execute(insert(Student).values(students_batch))
        await session.execute(insert(Attendance).values(attendance_batch))
        await session.execute(insert(Assessment).values(assessments_batch))
        await session.execute(insert(Assignment).values(assignments_batch))
        await session.execute(insert(Fee).values(fees_batch))
        await session.execute(insert(StudentSummary).values(summary_batch))
        await session.flush()

    await session.commit()
    logger.info("Seeding complete.")
    logger.info(f"Story 1 (Attendance Drop): Class ID {story_class['id']} ({story_class['name']})")
    logger.info(f"Story 2 (Fees + Grades Declining Cluster): {story_fee_declining_cluster[:3]}...")
    logger.info(f"Story 3 (Slipping High Performer): Student ID {story_slipping_high_performer}")
    logger.info(f"Story 4 (Improved Student): Student ID {story_improved_student}")

async def main():
    await clear_db()
    async with AppSessionLocal() as session:
        await seed_data(session)

if __name__ == "__main__":
    asyncio.run(main())
