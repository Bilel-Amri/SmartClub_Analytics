import os

URLS_CODE = """from django.urls import path
from . import views

urlpatterns = [
    path("chat/",         views.chat,         name="chat"),
    path("chat/stream/",  views.chat_stream,  name="chat_stream"),
    path("chat/reset/",   views.reset_chat,   name="chat_reset"),
    path("chat/history/", views.chat_history, name="chat_history"),
]
"""

SESSION_CODE = """from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

HISTORY_TTL_SECONDS = 2 * 60 * 60
_memory_store: dict[str, list] = {}

def load_history(session_key: str) -> list[dict]:
    try:
        from django.core.cache import cache
        raw = cache.get(session_key)
        if raw is None: return []
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception as exc:
        logger.warning("Cache unavailable (%s), using in-memory store.", exc)
        return list(_memory_store.get(session_key, []))

def save_history(session_key: str, history: list[dict]) -> None:
    to_save = [m for m in history if m.get("role") != "system"]
    try:
        from django.core.cache import cache
        cache.set(session_key, json.dumps(to_save), timeout=HISTORY_TTL_SECONDS)
    except Exception as exc:
        logger.warning("Cache save failed (%s), using in-memory store.", exc)
        _memory_store[session_key] = to_save

def clear_history(session_key: str) -> None:
    try:
        from django.core.cache import cache
        cache.delete(session_key)
    except Exception as exc:
        logger.warning("Cache clear failed (%s).", exc)
    _memory_store.pop(session_key, None)
"""

# Saving views, agent, llm_client, and tools using straight writes
import sys

def write_file(filename, content):
    filepath = os.path.join(os.path.dirname(__file__), "chat_llm", filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Updated {filename}")

if __name__ == "__main__":
    write_file("urls.py", URLS_CODE)
    write_file("session.py", SESSION_CODE)
