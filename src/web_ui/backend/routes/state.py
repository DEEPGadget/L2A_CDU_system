"""Full snapshot endpoint — used by Dashboard on mount to hydrate before
the WebSocket stream starts pushing deltas.

Returns every `sensor:*` / `control:*` / `alarm:*` / `comm:*` key as a
flat dict[str, str]. Values that aren't present in Redis are omitted
rather than nulled — the frontend should treat missing keys as
'no data yet'.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from src.web_ui.backend.redis_client import get_redis

router = APIRouter(prefix="/api/state", tags=["state"])

_PATTERNS = ("sensor:*", "control:*", "alarm:*", "comm:*")


@router.get("")
async def get_state(r: Redis = Depends(get_redis)) -> dict:
    out: dict[str, object] = {}
    for pattern in _PATTERNS:
        async for key in r.scan_iter(match=pattern, count=200):
            ktype = await r.type(key)
            if ktype == "hash":
                out[key] = await r.hgetall(key)
            elif ktype == "string":
                out[key] = await r.get(key)
            # other types (list/set/stream) aren't used by L2A yet — skip
    return out
