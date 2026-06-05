"""Cooling diagram endpoint — serves the same SVG the Local UI renders.

Single source of truth: src/local_ui/assets/cooling_health.svg. The web
frontend fetches the raw SVG (with {TOKEN} placeholders), substitutes live
values + colors client-side, and renders it. Keeping one file means the Local
and Web diagrams never drift.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

router = APIRouter(prefix="/api/diagram", tags=["diagram"])

# .../src/web_ui/backend/routes/diagram.py → parents[3] = src/
_SVG_PATH = (
    Path(__file__).resolve().parents[3]
    / "local_ui" / "assets" / "cooling_health.svg"
)


@router.get("", response_class=PlainTextResponse)
async def get_diagram() -> PlainTextResponse:
    try:
        svg = _SVG_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="cooling diagram not found")
    return PlainTextResponse(svg, media_type="image/svg+xml")
