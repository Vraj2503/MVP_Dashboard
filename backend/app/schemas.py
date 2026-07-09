"""Pydantic request/response schemas.

Kept intentionally lean - one file per concern in larger projects is fine,
but for an MVP a single module reduces indirection.
"""
from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional, Generic, TypeVar

from pydantic import BaseModel, Field, model_validator, field_validator


# --- Common -----------------------------------------------------------------

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    pages: int

# --- Dashboard --------------------------------------------------------------


class MetricSeries(BaseModel):
    """A labelled (label, value) series used for sparklines & trend charts."""
    label: str
    value: float


class StaticDashboardResponse(BaseModel):
    institution: Dict[str, Any]
    attendance_trend: List[MetricSeries]
    grade_trend: List[MetricSeries]
    assignment_submission_rate: float
    fee_outstanding: float
    fee_collected: float
    class_breakdown: List[Dict[str, Any]]


class WidgetCard(BaseModel):
    id: str
    title: str
    severity: Literal["neutral", "ok", "warn", "danger"]
    primary_value: Any = None
    secondary: Optional[str] = None
    narrative: Optional[str] = None
    recommendations: Optional[List[str]] = None
    breakdown: Optional[str] = None
    sparkline: Optional[List[float]] = None
    rationale: Optional[str] = None          # why this widget was ranked here


class AdaptiveDashboardResponse(BaseModel):
    widgets: List[WidgetCard]
    generated_at: datetime


# --- Chat -------------------------------------------------------------------


class ChatRequest(BaseModel):
    question: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: Optional[str] = None
    sql: Optional[str] = None
    rows: Optional[List[Dict[str, Any]]] = None
    columns: Optional[List[str]] = None
    confidence: Optional[float] = None
    clarification_needed: bool = False
    choices: Optional[List[str]] = None
    chart_hint: Optional[str] = None   # kpi | line | bar | pie | table
    log_id: Optional[int] = None
    session_id: Optional[str] = None


class ChatFeedback(BaseModel):
    log_id: int
    feedback: Literal[-1, 0, 1]


# --- What-if ----------------------------------------------------------------


class WhatIfDelta(BaseModel):
    attendance_delta: float = 0.0     # percentage points e.g. +10
    grade_delta: float = 0.0          # percentage points
    assignment_miss_delta: float = 0.0
    fee_overdue_delta: float = 0.0


class WhatIfRequest(BaseModel):
    scope: Literal["institution", "class", "student"] = "institution"
    grade: Optional[int] = None
    section: Optional[str] = None
    student_ids: Optional[List[int]] = None
    changes: WhatIfDelta
    mode: Literal["simulate", "solver"] = "simulate"
    target_metric: Optional[Literal["attendance", "grade_avg", "pass_rate"]] = None
    target_value: Optional[float] = None
    save: bool = False                # persist as observation in chat_logs? optional


class WhatIfResponse(BaseModel):
    before: Dict[str, Any]
    after: Dict[str, Any]
    student_shifts: List[Dict[str, Any]]    # tier-up / tier-down transitions
    narrative: str
    solved_to: Optional[Dict[str, Any]] = None   # populated in solver mode


# --- Alerts / Digests -------------------------------------------------------


class AlertOut(BaseModel):
    id: int
    type: str
    student_id: Optional[int]
    severity: str
    message: str
    suggested_action: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class AlertStatusUpdate(BaseModel):
    status: Literal["open", "ack", "dismissed"]


class DigestOut(BaseModel):
    id: int
    period_start: date
    period_end: date
    content: Dict[str, Any]
    created_at: datetime


# --- Observability ----------------------------------------------------------


class ObservabilitySummary(BaseModel):
    total_queries: int
    success_rate: float
    avg_latency_ms: float
    failed_queries: int
    feedback_ratio: float         # +1 / total_feedback
    golden_pass_rate: Optional[float] = None
    last_run_at: Optional[datetime] = None


class GoldenTestOut(BaseModel):
    id: int
    name: str
    question: str
    last_passed: Optional[bool] = None
    last_answer: Optional[str] = None
    last_sql: Optional[str] = None
    last_run_at: Optional[datetime] = None


# --- Academics -------------------------------------------------------------

class CourseBase(BaseModel):
    code: str
    name: str
    credits: int = Field(default=3, gt=0)
    department_id: int = Field(gt=0)

class CourseCreate(CourseBase):
    pass

class CourseOut(CourseBase):
    id: int
    class Config:
        from_attributes = True

class ClassGroupBase(BaseModel):
    name: str
    grade: int
    section: str
    teacher_id: Optional[int] = None

class ClassGroupCreate(ClassGroupBase):
    grade: int = Field(ge=9, le=12)
    section: str = Field(min_length=1, max_length=1, pattern=r"^[A-Ea-e]$")

class ClassGroupOut(ClassGroupBase):
    id: int
    teacher_name: Optional[str] = None
    class Config:
        from_attributes = True

class TeacherBase(BaseModel):
    name: str
    subject: str

class TeacherCreate(TeacherBase):
    pass

class TeacherOut(TeacherBase):
    id: int
    class Config:
        from_attributes = True


# --- Students --------------------------------------------------------------

class StudentBase(BaseModel):
    name: str
    grade: int
    section: str
    enrollment_date: date
    parent_contact: str
    gender: str
    dob: date

class StudentCreate(StudentBase):
    grade: int = Field(ge=9, le=12)
    section: str = Field(min_length=1, max_length=1, pattern=r"^[A-Ea-e]$")

    @field_validator("dob")
    @classmethod
    def dob_must_be_past(cls, v: date):
        if v >= date.today():
            raise ValueError("Date of birth must be in the past")
        return v

class StudentOut(StudentBase):
    id: int
    attendance_rate: Optional[float] = None
    grade_avg: Optional[float] = None
    class Config:
        from_attributes = True

class SubjectGrade(BaseModel):
    subject: str
    average_score: float
    assessment_count: int

class StudentDetail(StudentOut):
    grades: List[SubjectGrade] = Field(default_factory=list)


# --- Attendance ------------------------------------------------------------

class AttendanceRecordBase(BaseModel):
    student_id: int
    status: str
    period: Optional[int] = None

class AttendanceClassView(BaseModel):
    student_id: int
    student_name: str
    status: Optional[str] = None

class AttendanceBulkCreate(BaseModel):
    date: date
    grade: int
    section: str
    records: List[AttendanceRecordBase]

class AttendanceOut(BaseModel):
    id: int
    student_id: int
    date: date
    status: str
    period: Optional[int] = None
    class Config:
        from_attributes = True

class StudentCalendarDay(BaseModel):
    date: date
    status: str

class ClassCalendarDay(BaseModel):
    date: date
    total: int
    present: int
    percentage: float
    is_holiday: bool

# --- Academics Students Tab ------------------------------------------------

class AcademicStudentOut(BaseModel):
    id: int
    name: str
    grade: int
    section: str
    attendance_rate: Optional[float] = None
    grade_avg: Optional[float] = None
    overdue_fees: int = 0
    
    class Config:
        from_attributes = True

class StudentAssessmentOut(BaseModel):
    id: int
    subject: str
    type: str
    score: float
    max_score: float
    date: date
    
    class Config:
        from_attributes = True

class AssessmentCreate(BaseModel):
    subject: str
    type: str
    score: float = Field(ge=0)
    max_score: float = Field(default=100.0, gt=0)
    date: date

    @model_validator(mode='after')
    def check_score(self) -> 'AssessmentCreate':
        if self.score > self.max_score:
            raise ValueError("score cannot be greater than max_score")
        return self

class AssessmentUpdate(BaseModel):
    subject: Optional[str] = None
    type: Optional[str] = None
    score: Optional[float] = Field(default=None, ge=0)
    max_score: Optional[float] = Field(default=None, gt=0)
    date: Optional[date] = None

    @model_validator(mode='after')
    def check_score(self) -> 'AssessmentUpdate':
        if self.score is not None and self.max_score is not None:
            if self.score > self.max_score:
                raise ValueError("score cannot be greater than max_score")
        return self

