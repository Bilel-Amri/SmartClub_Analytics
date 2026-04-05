"""
monitoring/middleware.py
========================
Intercepts every HTTP request, measures its latency and response size,
then records it in the in-memory store.

Endpoint normalisation:
    /api/v2/physio/simulator/42/  →  /api/v2/physio/simulator/{id}/
"""

import re
import time

from monitoring.store import record_request

# Regex: turn numeric segments into the literal "{id}"
_ID_RE = re.compile(r'/\d+')


def _normalise(path: str) -> str:
    path = _ID_RE.sub("/{id}", path)
    # Strip trailing slash for consistency
    return path.rstrip("/") or "/"


# Map long paths to short human-readable labels used in charts
_LABEL_MAP = {
    "/api/scout/players":               "scout/players",
    "/api/scout/contracts":             "scout/contracts",
    "/api/v2/physio/squad/daily-risk": "physio/squad-daily-risk",
    "/api/v2/physio/simulator/assess":  "physio/simulator",
    "/api/v2/physio/absence/predict":   "physio/absence",
    "/api/v2/physio/players/profiles":  "physio/profiles",
    "/api/v2/physio/ai/explain":        "physio/ai-explain",
    "/api/v2/physio/ml/health":         "physio/ml-health",
    "/api/v2/physio/similarity/seed":   "physio/similarity-seed",
    "/api/nutri/foods":            "nutri/foods",
    "/api/nutri/meal-calc":        "nutri/meal",
    "/api/nutri/generate-plan":    "nutri/plan",
    "/api/nutri/live-feedback":    "nutri/live-feedback",
    "/api/nutri/plans":            "nutri/plans",
    "/api/nutri/supplements":      "nutri/supplements",
    "/api/chat":                   "chat",
    "/api/chat-llm":               "chat-llm",
    "/api/chat-llm/stream":        "chat-llm-stream",
    "/api/auth/token":             "auth/token",
    "/api/auth/token/refresh":     "auth/refresh",
    "/api/auth/me":                "auth/me",
    "/api/dashboard/summary":      "dashboard",
    "/api/monitoring/metrics":     "monitoring",
}


def _label(path: str) -> str:
    return _LABEL_MAP.get(path, path.split("/")[2] if path.startswith("/api/") else path)


class MetricsMiddleware:
    """WSGI-compatible middleware — works with Django's default stack."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        t0       = time.perf_counter()
        response = self.get_response(request)
        latency  = (time.perf_counter() - t0) * 1000          # ms

        if request.path.startswith(("/api/", "/admin/")):
            norm = _normalise(request.path)
            record_request(
                endpoint   = _label(norm),
                status     = response.status_code,
                latency_ms = round(latency, 3),
                size_bytes = int(getattr(response, "content", None) and len(response.content) or 0),
            )

        return response
