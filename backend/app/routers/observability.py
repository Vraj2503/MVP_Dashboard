from typing import List, Any
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete

from ..db import get_db
from ..schemas import ObservabilitySummary, GoldenTestOut
from ..services import observability, golden_tests
from ..models import ChatLog

router = APIRouter()

@router.get("/summary", response_model=ObservabilitySummary)
async def get_summary(db: AsyncSession = Depends(get_db)):
    metrics = await observability.summary(db)
    
    gt = golden_tests.latest()
    if gt:
        metrics["golden_pass_rate"] = gt.get("pass_rate")
        metrics["last_run_at"] = gt.get("run_at")
        
    return ObservabilitySummary(**metrics)

@router.get("/failed")
async def get_failed(db: AsyncSession = Depends(get_db)):
    return await observability.recent_failed(db, limit=20)

@router.get("/golden")
async def get_golden():
    return golden_tests.latest() or {}

@router.post("/golden/run")
async def run_golden(db: AsyncSession = Depends(get_db)):
    res = await golden_tests.run_all(db)
    return res

@router.delete("/failed")
async def clear_failed(db: AsyncSession = Depends(get_db)):
    """Clear all failed chat logs."""
    result = await db.execute(
        delete(ChatLog).where(ChatLog.success.is_(False))
    )
    await db.commit()
    return {"status": "ok", "deleted": result.rowcount}

@router.delete("/logs")
async def clear_all_logs(db: AsyncSession = Depends(get_db)):
    """Purge all chat logs (resets observability metrics)."""
    result = await db.execute(delete(ChatLog))
    await db.commit()
    return {"status": "ok", "deleted": result.rowcount}
