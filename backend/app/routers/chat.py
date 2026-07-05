from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_ro_db, get_db
from ..schemas import ChatRequest, ChatResponse, ChatFeedback
from ..services.nl2sql import run_pipeline
from ..services.observability import record_chat, record_feedback, get_session_history
import uuid

router = APIRouter()

@router.post("", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, ro_db: AsyncSession = Depends(get_ro_db), app_db: AsyncSession = Depends(get_db)):
    session_id = req.session_id or uuid.uuid4().hex
    
    history = await get_session_history(app_db, session_id)
    result = await run_pipeline(ro_db, req.question, session_history=list(history))
    
    # Log to observability
    import json
    log_id = await record_chat(
        app_db,
        user_id=req.user_id,
        question=req.question,
        generated_sql=result.sql,
        result_json=result.answer,
        latency_ms=result.latency_ms,
        success=(result.error is None),
        tokens=result.tokens,
        error=result.error,
        session_id=session_id
    )
    
    if result.error and not result.clarification_needed:
        # We don't raise 500, we return the error in the answer for the UI to display gracefully
        pass
        
    return ChatResponse(
        answer=result.answer,
        sql=result.sql,
        rows=result.rows,
        columns=result.columns,
        confidence=result.confidence,
        clarification_needed=bool(result.clarification_needed),
        choices=result.choices,
        chart_hint=result.chart_hint,
        log_id=log_id,
        session_id=session_id
    )

@router.post("/feedback")
async def chat_feedback_endpoint(req: ChatFeedback, db: AsyncSession = Depends(get_db)):
    await record_feedback(db, req.log_id, req.feedback)
    return {"status": "ok"}
