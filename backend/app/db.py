"""Async SQLAlchemy wiring.

Two engines:
- `engine`      : connects to APP_DATABASE_URL (read/write).
- `ro_engine`   : connects to READONLY_DATABASE_URL (the SELECT-only MySQL user
                  used exclusively by the NL2SQL pipeline).

`get_db` provides request-scoped sessions bound to the app engine.
`get_ro_db` provides request-scoped sessions bound to the read-only engine.

Tables must be created once with `Base.metadata.create_all(...)`; in container
deployments prefer running the migration/init script (see init-mysql.sql).
"""
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings


class Base(DeclarativeBase):
    """Single declarative base shared by all ORM models."""


settings = get_settings()

engine = create_async_engine(
    settings.app_database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    future=True,
)

ro_engine = create_async_engine(
    settings.readonly_database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    future=True,
)

AppSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

ReadOnlySessionLocal = async_sessionmaker(
    ro_engine, expire_on_commit=False, class_=AsyncSession
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: app DB session."""
    async with AppSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_ro_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: read-only DB session (NL2SQL)."""
    async with ReadOnlySessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
