"""Thin async wrapper around `groq`.

Two responsibilities:
1. Initialise a single `AsyncGroq` client at import time.
2. Provide `generate_json(prompt, ...)` and `generate_text(prompt, ...)`
   helpers that:
     - Apply the same model name + temperature defaults.
     - Reject non-JSON outputs when JSON is requested.
     - Optionally forward traces to Langfuse when LANGFUSE_ENABLED is true.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

from groq import AsyncGroq

from ..config import get_settings

settings = get_settings()
logger = logging.getLogger("groq")

_client: Optional[AsyncGroq] = None
_langfuse = None


def get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=settings.groq_api_key)
    return _client


def init_langfuse() -> None:
    """Initialise Langfuse if enabled and credentials are present."""
    global _langfuse
    if not settings.langfuse_enabled:
        return
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        logger.warning("LANGFUSE_ENABLED=true but credentials are missing; skipping.")
        return
    try:
        from langfuse import Langfuse
        _langfuse = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        logger.info("Langfuse initialised at %s", settings.langfuse_host)
    except Exception as e:
        logger.warning("Langfuse init failed: %s", e)


async def generate_text(prompt: str, *, temperature: float = 0.4, max_tokens: int = 1024) -> str:
    """Plain text generation. Returns the trimmed response or a fallback string."""
    start = time.perf_counter()
    
    if _langfuse:
        try:
            with _langfuse.start_as_current_span(name="groq.generate_text") as span:
                resp = await get_client().chat.completions.create(
                    model=settings.llm_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                out = resp.choices[0].message.content or ""
                span.update(output=out)
                return out.strip()
        except Exception:
            pass

    resp = await get_client().chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    out = (resp.choices[0].message.content or "").strip()
    logger.debug("Groq text in %.2fs -> %d chars", time.perf_counter() - start, len(out))
    return out


async def generate_json(prompt: str, *, temperature: float = 0.2, max_tokens: int = 2048) -> Dict[str, Any]:
    """Generate JSON explicitly.

    Falls back to extracting a JSON object from a fenced code block if needed.
    Raises ValueError if no parseable JSON is returned.
    """
    if _langfuse:
        try:
            with _langfuse.start_as_current_span(name="groq.generate_json") as span:
                resp = await get_client().chat.completions.create(
                    model=settings.llm_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"}
                )
                out = resp.choices[0].message.content or ""
                span.update(output=out)
                return _parse_json(out)
        except Exception:
            pass

    resp = await get_client().chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"}
    )
    out = resp.choices[0].message.content or ""
    return _parse_json(out)


def _parse_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise ValueError("Empty Groq response")

    # Strip code fences if present
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3]
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        # last resort: find a top-level JSON object
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise ValueError(f"Could not parse JSON from Groq: {e}") from e
