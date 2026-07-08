from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import engine, Base
from .services.cache import init_redis, close_redis
from .services.llm_client import init_langfuse
from .scheduler import start_scheduler, stop_scheduler

from .routers import dashboard, chat, digest, observability, alerts, academics, students, attendance

settings = get_settings()
logger = logging.getLogger("app")


from .services.nl2sql import load_schema_ddl

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init DB schema if it doesn't exist (relies on models being imported)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # Auto-sync NL2SQL schema DDL from the database
    await load_schema_ddl(engine)
    
    # Init external services
    await init_redis()
    init_langfuse()
    
    # Start background scheduler (APScheduler)
    start_scheduler()
    
    logger.info("Application startup complete.")
    yield
    
    # Teardown
    stop_scheduler()
    await close_redis()
    await engine.dispose()
    logger.info("Application shutdown complete.")


app = FastAPI(
    title="School Management MVP API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(digest.router, prefix="/api/digests", tags=["digests"])
app.include_router(observability.router, prefix="/api/observability", tags=["observability"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(academics.router, prefix="/api/academics", tags=["academics"])
app.include_router(students.router, prefix="/api/students", tags=["students"])
app.include_router(attendance.router, prefix="/api/attendance", tags=["attendance"])

@app.get("/")
async def root():
    return {"status": "ok", "app": "School Management MVP API"}
