"""Alerts API router.

Endpoints for listing, filtering, updating, and manually triggering alert scans.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import Alert, AlertStatus, AlertSeverity
from ..schemas import AlertOut, AlertStatusUpdate
from ..services.alert_engine import run_all_checks

router = APIRouter()


@router.get("", response_model=List[AlertOut])
async def list_alerts(
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None, alias="type"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List alerts with optional filters."""
    q = select(Alert).order_by(Alert.created_at.desc())

    if severity:
        try:
            q = q.where(Alert.severity == AlertSeverity(severity))
        except ValueError:
            pass

    if status:
        try:
            q = q.where(Alert.status == AlertStatus(status))
        except ValueError:
            pass

    if alert_type:
        q = q.where(Alert.type == alert_type)

    q = q.offset(offset).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return rows


@router.get("/unread-count")
async def unread_count(db: AsyncSession = Depends(get_db)):
    """Return count of open alerts for badge display."""
    q = select(func.count(Alert.id)).where(Alert.status == AlertStatus.OPEN)
    count = (await db.execute(q)).scalar() or 0
    return {"count": count}


@router.patch("/{alert_id}")
async def update_alert_status(
    alert_id: int,
    body: AlertStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Acknowledge or dismiss an alert."""
    result = await db.execute(
        update(Alert)
        .where(Alert.id == alert_id)
        .values(status=AlertStatus(body.status))
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    await db.commit()
    return {"status": "ok"}


@router.post("/scan")
async def trigger_scan(db: AsyncSession = Depends(get_db)):
    """Manually trigger an alert scan."""
    alerts = await run_all_checks(db)
    return {
        "status": "ok",
        "alerts_created": len(alerts),
        "alerts": [
            {"id": a.id, "type": a.type, "severity": a.severity.value, "message": a.message}
            for a in alerts
        ],
    }
