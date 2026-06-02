"""History endpoint — proxies Prometheus range queries for the Dashboard's
history charts (M3).

The browser stays same-origin (nginx :80 → FastAPI :8000); this route forwards
to Prometheus (:9090) server-side so the UI never needs direct Prometheus
access or CORS. Metrics are produced by src/exporter (Redis → Prometheus pull).

    GET /api/history?query=<promql>&minutes=60&step=30
        → Prometheus /api/v1/query_range over [now-minutes, now]
        → returns the Prometheus `data` object {resultType, result}
"""

from __future__ import annotations

import re
import time

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/history", tags=["history"])

PROMETHEUS_URL = "http://localhost:9090"

# Allow only PromQL we expect from the dashboard (metric names + label matchers).
# Prevents this internal proxy from being used for arbitrary server-side calls.
_QUERY_RE = re.compile(r'^[A-Za-z_:][A-Za-z0-9_:]*(\{[A-Za-z0-9_=!~"\'`,.\- ]*\})?$')


@router.get("")
async def history(
    query: str = Query(..., description="PromQL metric selector, e.g. sensor_flow_rate"),
    minutes: int = Query(60, ge=1, le=7 * 24 * 60),
    step: int = Query(30, ge=1, le=3600),
) -> dict:
    if not _QUERY_RE.match(query):
        raise HTTPException(status_code=400, detail=f"unsupported query: {query!r}")

    end = time.time()
    start = end - minutes * 60
    params = {"query": query, "start": start, "end": end, "step": step}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{PROMETHEUS_URL}/api/v1/query_range", params=params)
        resp.raise_for_status()
        body = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"prometheus query failed: {exc}")

    if body.get("status") != "success":
        raise HTTPException(status_code=502, detail=f"prometheus error: {body.get('error')}")

    return body["data"]
