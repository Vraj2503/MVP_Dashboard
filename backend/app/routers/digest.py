from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
import json

from ..db import get_db
from ..models import Digest
from ..schemas import DigestOut
from ..services.digest_generator import generate_digest

router = APIRouter()

@router.get("", response_model=List[DigestOut])
async def list_digests(db: AsyncSession = Depends(get_db)):
    q = select(Digest).order_by(Digest.created_at.desc()).limit(10)
    res = (await db.execute(q)).scalars().all()
    out = []
    for d in res:
        out.append(DigestOut(
            id=d.id,
            period_start=d.period_start,
            period_end=d.period_end,
            content=json.loads(d.content_json),
            created_at=d.created_at
        ))
    return out

@router.post("/generate", response_model=DigestOut)
async def trigger_digest(db: AsyncSession = Depends(get_db)):
    d = await generate_digest(db)
    await db.commit()
    return DigestOut(
        id=d.id,
        period_start=d.period_start,
        period_end=d.period_end,
        content=json.loads(d.content_json),
        created_at=d.created_at
    )

@router.delete("/{digest_id}")
async def delete_digest(digest_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a single digest by ID."""
    result = await db.execute(delete(Digest).where(Digest.id == digest_id))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Digest not found")
    await db.commit()
    return {"status": "ok", "deleted": 1}

@router.delete("")
async def clear_all_digests(db: AsyncSession = Depends(get_db)):
    """Delete all digests."""
    result = await db.execute(delete(Digest))
    await db.commit()
    return {"status": "ok", "deleted": result.rowcount}
