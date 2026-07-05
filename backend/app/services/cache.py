"""Async Redis cache with graceful degradation.

If Redis is unreachable at runtime, every call falls back to the underlying
function and we don't raise - the system continues (just slower).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable, Optional

import redis.asyncio as aioredis

from ..config import get_settings

settings = get_settings()
logger = logging.getLogger("cache")

_redis: Optional[aioredis.Redis] = None


async def init_redis() -> None:
    global _redis
    try:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        await _redis.ping()
        logger.info("Redis ready: %s", settings.redis_url)
    except Exception as e:  # pragma: no cover
        logger.warning("Redis unavailable (%s) - cache disabled", e)
        _redis = None


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def get_json(key: str) -> Optional[Any]:
    if _redis is None:
        return None
    try:
        raw = await _redis.get(key)
    except Exception:
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def set_json(key: str, value: Any, ttl_seconds: int) -> None:
    if _redis is None:
        return
    try:
        await _redis.set(key, json.dumps(value, default=str), ex=ttl_seconds)
    except Exception as e:  # pragma: no cover
        logger.debug("Cache write failed for %s: %s", key, e)


async def with_cache(key: str, ttl: int, loader: Callable[[], Awaitable[Any]]) -> Any:
    """Loader cached by `key` for `ttl` seconds."""
    cached = await get_json(key)
    if cached is not None:
        return cached
    value = await loader()
    await set_json(key, value, ttl)
    return value
