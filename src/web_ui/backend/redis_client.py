"""Async Redis client singleton for the Web UI backend.

Uses redis.asyncio so FastAPI handlers can `await` without blocking the
event loop. One TCP connection (with the library's internal connection
pool) is shared across all requests for the process lifetime.
"""

from __future__ import annotations

import redis.asyncio as aioredis

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """Lazy singleton. Called from route handlers as a dependency."""
    global _client
    if _client is None:
        _client = aioredis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True,
        )
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
