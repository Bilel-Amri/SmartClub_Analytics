"""
monitoring/store.py
===================
Thread-safe in-memory metrics store shared across middleware, background
sampler and the view layer.  No external dependencies — pure stdlib.

Data retained:
  _requests   – deque of request records (max 10 000)
  _resources  – deque of resource samples taken every 5 s (max 720 → 1 h)
  _start_time – float, server start epoch
"""

import time
import threading
from collections import deque

_lock        = threading.Lock()
_requests    = deque(maxlen=10_000)   # [{ts, endpoint, status, latency_ms, size_bytes}]
_resources   = deque(maxlen=720)      # [{ts, cpu_pct, mem_mb, open_files}]
_start_time  = time.time()


# ── helpers ──────────────────────────────────────────────────────────────

def record_request(endpoint: str, status: int, latency_ms: float, size_bytes: int) -> None:
    with _lock:
        _requests.append({
            "ts":         time.time(),
            "endpoint":   endpoint,
            "status":     status,
            "latency_ms": latency_ms,
            "size_bytes": size_bytes,
        })


def record_resources(cpu_pct: float, mem_mb: float, open_files: int) -> None:
    with _lock:
        _resources.append({
            "ts":         time.time(),
            "cpu_pct":    cpu_pct,
            "mem_mb":     mem_mb,
            "open_files": open_files,
        })


def snapshot() -> dict:
    """Return a **copy** of both stores – safe to iterate outside the lock."""
    with _lock:
        return {
            "requests":   list(_requests),
            "resources":  list(_resources),
            "start_time": _start_time,
        }
