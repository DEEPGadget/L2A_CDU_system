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

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.web_ui.backend.redis_client import close_redis, get_redis
from src.web_ui.backend.routes import control, state

log = logging.getLogger(__name__)

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
