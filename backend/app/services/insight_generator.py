"""Per-widget Gemini narratives for the Adaptive Dashboard.

Every widget on the adaptive dashboard surfaces a short, plain-English
insight sentence. These are generated lazily, then cached for 1 hour.

The prompt is concise so the narrative stays short, and we cache aggressively
because the underlying data only changes a few times a day.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from .llm_client import generate_json, generate_text
from . import cache
from ..config import get_settings

settings = get_settings()
logger = logging.getLogger("insight")


SYSTEM_PROMPT = (
    "You write concise insights for a school admin dashboard. "
    "Be specific: include the numbers you were given. No marketing tone. "
    "Output JSON only with this shape: "
    '{"narrative": "<2-3 sentence trend-aware insight>", '
    '"recommendations": ["<actionable recommendation 1>", "<actionable recommendation 2>"], '
    '"breakdown": "<1 sentence about the most affected grades/departments>"}'
)


async def narrative(widget_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Return a structured insight dict for a widget.

    Returns: {"narrative": str, "recommendations": [str], "breakdown": str|None}

    `context` should be plain JSON of the relevant metrics.
    Cached for `narrative_cache_ttl` seconds.
    """
    cache_key = f"narrative:{widget_id}:{hash(tuple(sorted(str(k) for k in context)))}"

    async def _load():
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Widget: {widget_id}\n"
            f"Context: {json.dumps(context, default=str)}\n"
            "Return JSON only."
        )
        try:
            result = await generate_json(prompt, temperature=0.3, max_tokens=300)
            return {
                "narrative": result.get("narrative", ""),
                "recommendations": result.get("recommendations", []),
                "breakdown": result.get("breakdown"),
            }
        except Exception as e:
            logger.debug("Narrative fallback for %s: %s", widget_id, e)
            return _fallback(widget_id, context)

    return await cache.with_cache(
        cache_key, settings.narrative_cache_ttl, _load
    )


async def narrative_text(widget_id: str, context: Dict[str, Any]) -> str:
    """Backward-compatible: return just the narrative string."""
    result = await narrative(widget_id, context)
    if isinstance(result, dict):
        return result.get("narrative", "")
    return str(result)


def _fallback(widget_id: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic fallback so the UI never shows a blank narrative."""
    narrative_text = ""
    recommendations: List[str] = []
    breakdown: Optional[str] = None

    if widget_id == "attendance":
        a = ctx.get("attendance_rate")
        delta = ctx.get("delta")
        if a is None:
            narrative_text = "Attendance metrics unavailable."
        else:
            sign = "▲" if (delta or 0) > 0 else "▼" if (delta or 0) < 0 else "·"
            narrative_text = f"Institution-wide attendance is {a:.0f}% ({sign} {abs(delta or 0):.0f} pts vs last week)."
        grade_data = ctx.get("grade_breakdown")
        if grade_data:
            worst = grade_data[0] if grade_data else None
            if worst:
                breakdown = f"Grade {worst.get('grade', '?')} has the lowest attendance at {worst.get('rate', 0):.0f}%."
                recommendations = [f"Focus outreach on Grade {worst.get('grade', '?')} students with chronic absences."]
    elif widget_id == "at_risk":
        n = ctx.get("count", 0)
        pct = ctx.get("pct", 0)
        narrative_text = f"{n} students ({pct:.0f}%) currently in the At-Risk tier."
        grade_data = ctx.get("grade_breakdown")
        if grade_data:
            worst = grade_data[0] if grade_data else None
            if worst:
                breakdown = f"Grade {worst.get('grade', '?')} accounts for {worst.get('count', 0)} at-risk students."
                recommendations = [
                    f"Schedule intervention sessions for Grade {worst.get('grade', '?')} at-risk students.",
                    "Consider parent-teacher conferences for students with risk scores above 70."
                ]
    elif widget_id == "fees":
        outstanding = ctx.get("outstanding", 0)
        overdue = ctx.get("overdue_count", 0)
        narrative_text = f"${outstanding:,.0f} outstanding across {overdue} overdue invoices."
        recommendations = ["Send payment reminders to families with overdue invoices.", "Review fee waiver eligibility for at-risk students."]
    elif widget_id == "class_attendance_drop":
        cls = ctx.get("class", "a class")
        drop = ctx.get("drop", 0)
        narrative_text = f"{cls} has dropped {drop:.0f} percentage points in the last 7 days."
    elif widget_id == "slipping_high_performer":
        narrative_text = "A previously top-tier student is trending downward on recent assessments."
    elif widget_id == "story_high_performer":
        narrative_text = "A student we previously flagged as slipping has rebounded this week."
    else:
        narrative_text = "Live metric."

    return {
        "narrative": narrative_text,
        "recommendations": recommendations,
        "breakdown": breakdown,
    }
