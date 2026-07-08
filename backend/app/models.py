"""SQLAlchemy ORM models - one class per table in the spec.

Index design notes:
- Heavy filters (student_id, date, grade, section) get composite indexes that
  match expected WHERE / ORDER BY patterns.
- `student_summary`, `chat_logs`, `alerts`, `digests` are dashboard-side reads;
  indexes there optimise widget/observation list endpoints.
"""
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, ForeignKey, Index, Integer,
    String, Text, Enum as SAEnum,
)
from sqlalchemy.orm import relationship
import enum

from .db import Base


class GenderEnum(str, enum.Enum):
    M = "M"
    F = "F"
    OTHER = "Other"


class FeeStatus(str, enum.Enum):
    PAID = "Paid"
    PARTIAL = "Partial"
    UNPAID = "Unpaid"
    OVERDUE = "Overdue"


class RiskTier(str, enum.Enum):
    SAFE = "Safe"
    WATCH = "Watch"
    AT_RISK = "At-Risk"


class AlertStatus(str, enum.Enum):
    OPEN = "open"
    ACK = "ack"
    DISMISSED = "dismissed"


class AlertSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# --- Core entities ---------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(80), nullable=False, unique=True, index=True)
    email = Column(String(120), nullable=False, unique=True)
    role = Column(String(40), nullable=False, default="admin")


class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    subject = Column(String(80), nullable=False, index=True)


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    department_id = Column(Integer, nullable=False, index=True)
    code = Column(String(20), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    credits = Column(Integer, nullable=False, default=3)


class ClassGroup(Base):
    """A section-level class (Grade X + Section Y)."""
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(80), nullable=False)
    grade = Column(Integer, nullable=False, index=True)
    section = Column(String(8), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=True)

    teacher = relationship("Teacher", lazy="joined")

    __table_args__ = (
        Index("ix_classes_grade_section", "grade", "section"),
    )


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False, index=True)
    grade = Column(Integer, nullable=False, index=True)
    section = Column(String(8), nullable=False, index=True)
    enrollment_date = Column(Date, nullable=False)
    parent_contact = Column(String(40), nullable=False)
    gender = Column(SAEnum(GenderEnum), nullable=False)
    dob = Column(Date, nullable=False)

    __table_args__ = (
        Index("ix_students_grade_section", "grade", "section"),
        Index("ix_students_enrollment_date", "enrollment_date"),
    )


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    status = Column(String(16), nullable=False)   # Present | Absent | Late | Excused
    period = Column(Integer, nullable=True)       # period index 1..N

    __table_args__ = (
        Index("ix_attendance_student_date", "student_id", "date"),
        Index("ix_attendance_date_status", "date", "status"),
    )


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    subject = Column(String(60), nullable=False, index=True)
    type = Column(String(40), nullable=False)     # Quiz | Midterm | Final | Project
    score = Column(Float, nullable=False)
    max_score = Column(Float, nullable=False, default=100.0)
    date = Column(Date, nullable=False, index=True)

    __table_args__ = (
        Index("ix_assessments_student_date", "student_id", "date"),
        Index("ix_assessments_subject_date", "subject", "date"),
    )


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    title = Column(String(160), nullable=False)
    submitted = Column(Boolean, nullable=False, default=True)
    on_time = Column(Boolean, nullable=False, default=True)
    score = Column(Float, nullable=True)
    due_date = Column(Date, nullable=False, index=True)

    __table_args__ = (
        Index("ix_assignments_student_due", "student_id", "due_date"),
    )


class Fee(Base):
    __tablename__ = "fees"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    term = Column(String(40), nullable=False)
    amount_due = Column(Float, nullable=False)
    amount_paid = Column(Float, nullable=False, default=0.0)
    due_date = Column(Date, nullable=False, index=True)
    status = Column(SAEnum(FeeStatus), nullable=False, index=True)

    __table_args__ = (
        Index("ix_fees_student_status", "student_id", "status"),
        Index("ix_fees_due_date_status", "due_date", "status"),
    )


class FeeInvoice(Base):
    __tablename__ = "fee_invoices"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    term = Column(String(40), nullable=False)
    amount = Column(Float, nullable=False)
    due_date = Column(Date, nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True) # e.g., Unpaid, Paid, Partial


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("fee_invoices.id"), nullable=False, index=True)
    amount_paid = Column(Float, nullable=False)
    payment_date = Column(DateTime, nullable=True, index=True)
    method = Column(String(50), nullable=True) # e.g., Credit Card, Cash


class BehaviorNote(Base):
    __tablename__ = "behavior_notes"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=True)
    note = Column(Text, nullable=False)
    severity = Column(String(16), nullable=False)  # info | warn | serious
    date = Column(Date, nullable=False, index=True)


# --- Materialised / event tables -------------------------------------------


class StudentSummary(Base):
    """Materialised per-student stats. Recomputed nightly by the scheduler."""
    __tablename__ = "student_summary"

    student_id = Column(Integer, ForeignKey("students.id"), primary_key=True)
    attendance_rate = Column(Float, nullable=False, default=0.0)
    grade_avg = Column(Float, nullable=False, default=0.0)
    assignment_miss_rate = Column(Float, nullable=False, default=0.0)
    fee_overdue_factor = Column(Float, nullable=False, default=0.0)
    risk_score = Column(Float, nullable=False, default=0.0, index=True)
    risk_tier = Column(SAEnum(RiskTier), nullable=False, index=True)
    previous_risk_tier = Column(SAEnum(RiskTier), nullable=True, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ChatLog(Base):
    """One row per NL2SQL request - used by the observability page."""
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(80), nullable=True, index=True)
    question = Column(Text, nullable=False)
    generated_sql = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    feedback = Column(Integer, nullable=True)  # 1 = thumbs up, -1 = down
    session_id = Column(String(36), index=True, nullable=True)
    latency_ms = Column(Integer, nullable=False, default=0)
    tokens = Column(Integer, nullable=False, default=0)
    success = Column(Boolean, nullable=False, default=True, index=True)
    error = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(80), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True, index=True)
    severity = Column(SAEnum(AlertSeverity), nullable=False, index=True)
    message = Column(Text, nullable=False)
    suggested_action = Column(Text, nullable=True)
    status = Column(SAEnum(AlertStatus), nullable=False, default=AlertStatus.OPEN, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class Digest(Base):
    __tablename__ = "digests"

    id = Column(Integer, primary_key=True, index=True)
    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False)
    content_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
