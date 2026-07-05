"""Risk scoring for students.

Formula (per spec):
    risk = (0.35 * (1 - attendance_rate)
          + 0.30 * (1 - grade_avg / 100)
          + 0.20 * assignment_miss_rate
          + 0.15 * fee_overdue_factor) * 100

Where:
- attendance_rate : proportion 0..1
- grade_avg       : percent 0..100
- assignment_miss_rate : proportion 0..1 (1 - submission rate)
- fee_overdue_factor   : 1.0 if status==Overdue, 0.5 if Partial/Unpaid, 0 if Paid

Tier mapping:
    0  <= score < 30 : Safe
    30 <= score < 60 : Watch
    60 <= score <=100: At-Risk

The pure-Python utils here are used by:
- seed.py during initial mock generation,
- scheduler.py for the nightly refresh,
- whatif_engine.py for simulation recompute.
"""
from dataclasses import dataclass
from typing import Iterable, List, Tuple

from ..models import RiskTier


W_ATTENDANCE = 0.35
W_GRADE = 0.30
W_ASSIGNMENT = 0.20
W_FEE = 0.15


@dataclass
class RiskInputs:
    attendance_rate: float      # 0..1
    grade_avg: float            # 0..100
    assignment_miss_rate: float # 0..1
    fee_overdue_factor: float   # 0, 0.5, 1


def compute_risk(inp: RiskInputs) -> Tuple[float, RiskTier]:
    att = max(0.0, min(1.0, inp.attendance_rate))
    grade_norm = max(0.0, min(1.0, inp.grade_avg / 100.0))
    miss = max(0.0, min(1.0, inp.assignment_miss_rate))
    fee = max(0.0, min(1.0, inp.fee_overdue_factor))

    score = (
        W_ATTENDANCE * (1 - att)
        + W_GRADE * (1 - grade_norm)
        + W_ASSIGNMENT * miss
        + W_FEE * fee
    ) * 100.0

    tier = (
        RiskTier.SAFE
        if score < 30
        else RiskTier.WATCH
        if score < 60
        else RiskTier.AT_RISK
    )
    return round(score, 2), tier


def apply_delta(base: RiskInputs, *, att_d: float = 0.0, grade_d: float = 0.0,
                miss_d: float = 0.0, fee_d: float = 0.0) -> RiskInputs:
    """Apply +/- percentage-point deltas to produce a simulated input set.

    - att_d, miss_d, fee_d are 0..1 deltas (e.g. 0.10 == +10 percentage points).
    - grade_d is percent points.
    """
    return RiskInputs(
        attendance_rate=max(0.0, min(1.0, base.attendance_rate + att_d)),
        grade_avg=max(0.0, min(100.0, base.grade_avg + grade_d)),
        assignment_miss_rate=max(0.0, min(1.0, base.assignment_miss_rate + miss_d)),
        fee_overdue_factor=max(0.0, min(1.0, base.fee_overdue_factor + fee_d)),
    )


def shifts_to_dict(before_tier: RiskTier, after_tier: RiskTier) -> str:
    order = {RiskTier.SAFE: 0, RiskTier.WATCH: 1, RiskTier.AT_RISK: 2}
    if before_tier == after_tier:
        return "unchanged"
    return "tier_down_to_safe" if order[after_tier] < order[before_tier] else "tier_up_at_risk"


def safe_div(num: float, den: float, default: float = 0.0) -> float:
    return num / den if den else default
