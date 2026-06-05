"""FastAPI app — Web UI backend.

Mounted endpoints:
  /api/state             — Redis snapshot (sensor/control/alarm/comm)
  /api/control           — mode / fan_curve / pump_duty CRUD
  /                      — SvelteKit static bundle (frontend/build/)

The frontend is built with SvelteKit's adapter-static in prerender mode,
so every route (/, /settings, …) is emitted as its own .html file and
served directly by StaticFiles — no SPA fallback wiring needed.

Run (dev):
    uvicorn src.web_ui.backend.main:app --reload --port 8000 --host 0.0.0.0

Run (prod): see scripts/services/cdu-web-backend.service.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.web_ui.backend.redis_client import close_redis, get_redis
from src.web_ui.backend.routes import control, diagram, history, state

log = logging.getLogger(__name__)

# Pub/Sub channels the dashboard listens to. sensor/comm/control publish to a
# channel named after the key; alarms are detected via keyspace events
# (Redis notify-keyspace-events = AKE) since they are SET/DEL, not published.
_WS_PATTERNS = ("sensor:*", "comm:*", "control:*", "__keyevent@0__:set", "__keyevent@0__:del")
_KEYEVENT_SET = "__keyevent@0__:set"
_KEYEVENT_DEL = "__keyevent@0__:del"

# frontend build is at src/web_ui/frontend/build/ (adapter-static).
_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "build"


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_redis()
    log.info("Web UI backend started (frontend dir exists=%s)", _FRONTEND_DIR.is_dir())
    yield
    await close_redis()
    log.info("Web UI backend shut down")


app = FastAPI(title="L2A CDU Web UI", lifespan=lifespan)
app.include_router(state.router)
app.include_router(control.router)
app.include_router(history.router)
app.include_router(diagram.router)


@app.websocket("/ws")
async def ws_live(websocket: WebSocket) -> None:
    """Live state stream. Pushes {key, value} deltas as Redis updates arrive.

    value is null for an alarm that was just cleared (key DEL). The client
    hydrates once via GET /api/state, then applies these deltas.
    """
    await websocket.accept()
    r = get_redis()
    pubsub = r.pubsub(ignore_subscribe_messages=True)
    await pubsub.psubscribe(*_WS_PATTERNS)

    async def pump() -> None:
        async for msg in pubsub.listen():
            if msg.get("type") not in ("message", "pmessage"):
                continue
            channel = msg["channel"]
            data = msg["data"]
            if channel in (_KEYEVENT_SET, _KEYEVENT_DEL):
                # Only forward alarm key lifecycle; sensor SETs already arrive
                # via their own pub/sub channel below.
                if not (isinstance(data, str) and data.startswith("alarm:")):
                    continue
                out = {"key": data, "value": "1" if channel == _KEYEVENT_SET else None}
            else:
                out = {"key": channel, "value": data}
            await websocket.send_json(out)

    pump_task = asyncio.create_task(pump())
    try:
        # We don't expect inbound frames; this await unblocks on disconnect.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        pump_task.cancel()
        await pubsub.aclose()


if _FRONTEND_DIR.is_dir():
    # html=True makes /<dir>/ resolve to <dir>/index.html so SvelteKit
    # prerendered routes (/settings/index.html, etc.) load on direct visit.
    app.mount(
        "/",
        StaticFiles(directory=str(_FRONTEND_DIR), html=True),
        name="frontend",
    )
else:
    @app.get("/")
    async def frontend_not_built() -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "error": "frontend not built",
                "hint": "cd src/web_ui/frontend && npm ci && npm run build",
            },
        )
