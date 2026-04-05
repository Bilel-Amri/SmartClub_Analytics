"""
monitoring/views.py
===================
GET /api/monitoring/metrics/

Aggregates the in-memory request + resource stores into Grafana-style
time-series panels ready for Recharts consumption.

Time window: last 30 minutes, split into 60 × 30-second buckets.
"""

import time
import math
from collections import defaultdict
from typing import List, Optional

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from monitoring.store import snapshot

# ── constants ────────────────────────────────────────────────────────────

WINDOW_SEC   = 30 * 60    # 30 minutes visible in charts
BUCKET_SEC   = 30         # one Recharts data-point per 30 s
N_BUCKETS    = WINDOW_SEC // BUCKET_SEC   # 60 buckets

RECENT_SEC   = 5 * 60     # 5-minute window for stat-card aggregations

# Endpoints considered "ML / prediction" requests
ML_ENDPOINTS = {
    "physio/squad-daily-risk",
    "physio/simulator",
    "physio/absence",
    "nutri/plan",
}


# ── helpers ───────────────────────────────────────────────────────────────

def _fmt_ts(epoch: float) -> str:
    """Format epoch to HH:MM label."""
    t = time.localtime(epoch)
    return f"{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}"


def _percentile(values: list, pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * pct / 100
    lo = math.floor(k)
    hi = math.ceil(k)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 2)


def _bucket_index(ts: float, now: float) -> Optional[int]:
    age = now - ts
    if age < 0 or age >= WINDOW_SEC:
        return None
    return N_BUCKETS - 1 - int(age // BUCKET_SEC)


# ── view ──────────────────────────────────────────────────────────────────

class MetricsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        data       = snapshot()
        now        = time.time()
        reqs       = data["requests"]
        res_samples = data["resources"]
        start_time = data["start_time"]
        uptime_sec = now - start_time

        # ── bucket initialisation ─────────────────────────────────────────
        bucket_ts = [
            now - WINDOW_SEC + (i + 0.5) * BUCKET_SEC
            for i in range(N_BUCKETS)
        ]

        # {bucket_idx: {endpoint: count}}
        by_ep    = [defaultdict(int) for _ in range(N_BUCKETS)]
        # {bucket_idx: {status_class: count}}
        by_st    = [defaultdict(int) for _ in range(N_BUCKETS)]
        # {bucket_idx: [latency_ms, …]}
        lat_raw  = [[] for _ in range(N_BUCKETS)]
        # {bucket_idx: total_bytes}
        bytes_b  = [0 for _ in range(N_BUCKETS)]

        # Recent window accumulators  (stat cards)
        recent_lat  = []
        recent_errs = 0
        recent_tot  = 0
        pred_count  = 0
        total_count = len(reqs)

        # Per-endpoint aggregations (all time, for bar charts)
        ep_lat_sum   = defaultdict(float)
        ep_lat_cnt   = defaultdict(int)
        ep_size_sum  = defaultdict(int)
        ep_size_cnt  = defaultdict(int)

        for r in reqs:
            ep        = r["endpoint"]
            st        = r["status"]
            lat       = r["latency_ms"]
            sz        = r["size_bytes"]
            age       = now - r["ts"]

            # Stat-card recent window
            if age <= RECENT_SEC:
                recent_tot  += 1
                recent_lat.append(lat)
                if st >= 500:
                    recent_errs += 1

            # Prediction count (all time)
            if ep in ML_ENDPOINTS:
                pred_count += 1

            # Endpoint / size aggregations (all time)
            ep_lat_sum[ep]  += lat
            ep_lat_cnt[ep]  += 1
            ep_size_sum[ep] += sz
            ep_size_cnt[ep] += 1

            # Time-bucket assignment
            bi = _bucket_index(r["ts"], now)
            if bi is not None:
                by_ep[bi][ep]                  += 1
                by_st[bi][str(st // 100) + "xx"] += 1
                lat_raw[bi].append(lat)
                bytes_b[bi] += sz

        # ── stat cards ────────────────────────────────────────────────────
        error_rate = round(recent_errs / recent_tot * 100, 1) if recent_tot else 0.0
        p97_lat    = _percentile(recent_lat, 97)
        mem_mb     = res_samples[-1]["mem_mb"]     if res_samples else 0.0
        uptime_h   = round(uptime_sec / 3600, 2)

        stats = {
            "total_requests":      total_count,
            "prediction_requests": pred_count,
            "error_rate_pct":      error_rate,
            "p97_latency_ms":      p97_lat,
            "uptime_hours":        uptime_h,
            "memory_mb":           round(mem_mb, 1),
        }

        # ── top-5 endpoints for chart colour assignment ───────────────────
        top_eps = sorted(ep_lat_cnt, key=lambda e: ep_lat_cnt[e], reverse=True)[:6]

        # ── request traffic by endpoint (line series per endpoint) ────────
        traffic_ep = [
            {
                "ts":   _fmt_ts(bucket_ts[i]),
                **{ep: by_ep[i].get(ep, 0) for ep in top_eps},
            }
            for i in range(N_BUCKETS)
        ]

        # ── request traffic by status ─────────────────────────────────────
        traffic_st = [
            {
                "ts":  _fmt_ts(bucket_ts[i]),
                "2xx": by_st[i].get("2xx", 0),
                "3xx": by_st[i].get("3xx", 0),
                "4xx": by_st[i].get("4xx", 0),
                "5xx": by_st[i].get("5xx", 0),
            }
            for i in range(N_BUCKETS)
        ]

        # ── latency percentiles (per bucket) ─────────────────────────────
        latency_pct = [
            {
                "ts":  _fmt_ts(bucket_ts[i]),
                "p50": _percentile(lat_raw[i], 50),
                "p95": _percentile(lat_raw[i], 95),
                "p99": _percentile(lat_raw[i], 99),
            }
            for i in range(N_BUCKETS)
        ]

        # ── avg latency by endpoint (bar chart) ──────────────────────────
        latency_by_ep = sorted(
            [
                {"endpoint": ep, "avg_ms": round(ep_lat_sum[ep] / ep_lat_cnt[ep], 2)}
                for ep in ep_lat_cnt
            ],
            key=lambda x: x["avg_ms"],
            reverse=True,
        )[:10]

        # ── resource samples → time-series ────────────────────────────────
        def _res_series(key):
            out = []
            for s in res_samples:
                bi = _bucket_index(s["ts"], now)
                if bi is not None:
                    out.append({"ts": _fmt_ts(s["ts"]), "value": round(s[key], 2)})
            return out or [{"ts": _fmt_ts(now), "value": 0}]

        # ── response size by endpoint ──────────────────────────────────────
        size_by_ep = sorted(
            [
                {"endpoint": ep, "avg_bytes": ep_size_sum[ep] // ep_size_cnt[ep]}
                for ep in ep_size_cnt if ep_size_sum[ep] > 0
            ],
            key=lambda x: x["avg_bytes"],
            reverse=True,
        )[:10]

        # ── throughput (bytes/sec per bucket) ────────────────────────────
        throughput = [
            {
                "ts":    _fmt_ts(bucket_ts[i]),
                "value": round(bytes_b[i] / BUCKET_SEC, 1),
            }
            for i in range(N_BUCKETS)
        ]

        return Response({
            "stats":          stats,
            "top_endpoints":  top_eps,
            "traffic_by_ep":  traffic_ep,
            "traffic_by_st":  traffic_st,
            "latency_pct":    latency_pct,
            "latency_by_ep":  latency_by_ep,
            "resources": {
                "cpu":        _res_series("cpu_pct"),
                "memory":     _res_series("mem_mb"),
                "open_files": _res_series("open_files"),
            },
            "size_by_ep":   size_by_ep,
            "throughput":   throughput,
        })
