from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

# History TTL: 2 hours of inactivity clears the session
HISTORY_TTL_SECONDS = 2 * 60 * 60

# Fallback in-memory store (single-process only, no persistence)
_memory_store: dict[str, list] = {}


def load_history(session_key: str) -> list[dict]:
    """Load conversation history. Returns [] if not found."""
    try:
        from django.core.cache import cache
        raw = cache.get(session_key)
        if raw is None:
            return []
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception as exc:
        logger.warning("Cache unavailable (%s), using in-memory store.", exc)
        return list(_memory_store.get(session_key, []))


def save_history(session_key: str, history: list[dict]) -> None:
    """
    Persist conversation history.
    Filters out system messages before saving.
    """
    to_save = [
        m for m in history
        if m.get("role") in ("user", "assistant")
        and m.get("content")  # skip None-content assistant msgs
    ]
    try:
        from django.core.cache import cache
        cache.set(session_key, json.dumps(to_save), timeout=HISTORY_TTL_SECONDS)
    except Exception as exc:
        logger.warning("Cache save failed (%s), using in-memory store.", exc)
        _memory_store[session_key] = to_save


def clear_history(session_key: str) -> None:
    """Delete conversation history for a session."""
    try:
        from django.core.cache import cache
        cache.delete(session_key)
    except Exception as exc:
        logger.warning("Cache clear failed (%s).", exc)
    _memory_store.pop(session_key, None)