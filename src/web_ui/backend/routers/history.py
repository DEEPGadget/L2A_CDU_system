from fastapi import APIRouter, Query
import httpx
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/history", tags=["history"])

PROMETHEUS_URL = "http://localhost:9090"


@router.get("/{metric}")
async def get_history(
    metric: str,
    hours: int = Query(default=1, ge=1, le=168),
) -> list:
    end = datetime.now()
    start = end - timedelta(hours=hours)
    params = {
        "query": metric,
        "start": start.isoformat() + "Z",
        "end": end.isoformat() + "Z",
        "step": "15s",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{PROMETHEUS_URL}/api/v1/query_range", params=params, timeout=10
        )
    resp.raise_for_status()
    return resp.json().get("data", {}).get("result", [])
