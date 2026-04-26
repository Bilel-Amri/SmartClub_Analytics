from __future__ import annotations

import json
import logging
import time as _time
from threading import Lock

from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .agent import run_agent
from .session import load_history, save_history, clear_history

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {"en", "fr", "ar", "tn"}

# ──────────────────────────────────────────────
# Bug 1 fix: deduplicate requests within 3-second window.
# The frontend retries on 401 (token refresh), sending two identical
# requests. We reject the second one to prevent run_agent() being
# called twice, which was doubling LLM latency.
# ──────────────────────────────────────────────
_recent_requests: dict[str, float] = {}
_recent_lock = Lock()
_DEDUP_WINDOW = 3.0  # seconds


def _is_duplicate_request(session_key: str, message: str) -> bool:
    """Return True if the same (session, message) was seen within DEDUP_WINDOW."""
    key = f"{session_key}:{hash(message)}"
    now = _time.monotonic()
    with _recent_lock:
        # Evict stale entries to prevent unbounded growth
        stale = [k for k, t in _recent_requests.items() if now - t > _DEDUP_WINDOW * 2]
        for k in stale:
            del _recent_requests[k]
        if key in _recent_requests and now - _recent_requests[key] < _DEDUP_WINDOW:
            return True
        _recent_requests[key] = now
        return False


# ──────────────────────────────────────────────
# POST /api/chat/
# ──────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chat(request):
    data     = request.data
    message  = (data.get("message") or "").strip()
    language = (data.get("language") or "en").lower()

    if not message:
        return Response(
            {"error": "Message cannot be empty."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if language not in SUPPORTED_LANGUAGES:
        language = "en"

    session_key = _get_session_key(request)

    # Bug 1: reject duplicate requests within the dedup window
    if _is_duplicate_request(session_key, message):
        logger.warning("Duplicate chat request rejected for session %s", session_key)
        return Response(
            {"error": "Duplicate request — please wait."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    history     = load_history(session_key)

    result = run_agent(
        user_message=message,
        history=history,
        language=language,
        streaming=False,
    )

    if result["error"]:
        logger.error("Agent error for session %s: %s", session_key, result["error"])
        return Response(
            {
                "reply":      _error_card(result["error"], language),
                "tool_calls": [],
                "error":      result["error"],
            },
            status=status.HTTP_200_OK,   # Return 200 so frontend shows the error card
        )

    save_history(session_key, result["updated_history"])

    return Response(
        {
            "reply":      result["reply"],
            "tool_calls": result["tool_calls"],
            "error":      None,
        },
        status=status.HTTP_200_OK,
    )


# ──────────────────────────────────────────────
# POST /api/chat/stream/
# ──────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chat_stream(request):
    # BUG 1 DIAGNOSTIC — shows every HTTP hit and its full call stack
    print(f"=== HTTP REQUEST RECEIVED: {request.method} {request.path} ===")
    import traceback
    traceback.print_stack(limit=8)

    data     = request.data
    message  = (data.get("message") or "").strip()
    language = (data.get("language") or "en").lower()

    if not message:
        return Response(
            {"error": "Message cannot be empty."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if language not in SUPPORTED_LANGUAGES:
        language = "en"

    session_key = _get_session_key(request)

    # Bug 1: reject duplicate requests within the dedup window
    if _is_duplicate_request(session_key, message):
        logger.warning("Duplicate stream request rejected for session %s", session_key)
        return Response(
            {"error": "Duplicate request — please wait."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    history     = load_history(session_key)

    result = run_agent(
        user_message=message,
        history=history,
        language=language,
        streaming=True,
    )

    # Do not save history immediately; wait until streaming finishes.
    # We will save it inside the generator's finally block.

    def event_stream():
        had_error = False
        try:
            for chunk in result["reply"]:
                chunk_str = chunk.strip()
                if "__ERROR__" in chunk_str or "failed_generation" in chunk_str:
                    had_error = True
                yield f"data: {chunk}\n\n"
        except Exception as exc:
            had_error = True
            logger.exception("Stream error for session %s", session_key)
            yield f"data: {json.dumps({'type': 'error', 'data': str(exc)})}\n\n"
        finally:
            if not had_error:
                save_history(session_key, result["updated_history"])

    response = StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream",
    )
    response["Cache-Control"]               = "no-cache"
    response["X-Accel-Buffering"]           = "no"    # disable nginx buffering
    response["Access-Control-Allow-Origin"] = "*"
    return response


# ──────────────────────────────────────────────
# DELETE /api/chat/reset/
# ──────────────────────────────────────────────

@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def reset_chat(request):
    """Clear the conversation history for this session."""
    session_key = _get_session_key(request)
    clear_history(session_key)
    return Response({"status": "cleared"}, status=status.HTTP_200_OK)


# ──────────────────────────────────────────────
# GET /api/chat/history/
# ──────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def chat_history(request):
    """Return the conversation history (excluding system prompts)."""
    session_key = _get_session_key(request)
    history = load_history(session_key)
    public_history = [m for m in history if m.get("role") != "system"]
    return Response({"history": public_history}, status=status.HTTP_200_OK)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _get_session_key(request) -> str:
    """Unique key per user (or per anonymous session)."""
    if request.user and request.user.is_authenticated:
        return f"chat_history_user_{request.user.pk}"
    return f"chat_history_anon_{request.session.session_key or 'default'}"


def _error_card(error_msg: str, language: str) -> str:
    cards = {
        "en": "⚠️ I ran into a technical issue. Please try again in a moment.",
        "fr": "⚠️ J'ai rencontré un problème technique. Veuillez réessayer dans un instant.",
        "ar": "⚠️ واجهت مشكلة تقنية. يرجى المحاولة مرة أخرى بعد لحظة.",
        "tn": "⚠️ صار مشكل تقني. حاول مرة أخرى بعد شوية.",
    }
    base = cards.get(language, cards["en"])
    logger.debug("Error card shown. Internal error: %s", error_msg)
    return base