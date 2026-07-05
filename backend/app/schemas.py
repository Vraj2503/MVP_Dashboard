"""Pydantic request/response schemas.

Kept intentionally lean - one file per concern in larger projects is fine,
but for an MVP a single module reduces indirection.
"""
from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


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
