"""UI router — operator dashboard surface.

Included by `ui.app:create_app()` onto the FastAPI app produced by
`core.app:create_app()`. Per the Day 10 alignment decision (DECISIONS
`[2026-05-01 Day 10]`), `core/` stays UI-free; this router and its
companion templates / static assets / wrapper factory live entirely
under `ui/`.

## Partial-render endpoints

`GET /partials/health-bar` composes the existing `/health` payload
with `/stats/top-tools` server-side via direct handler calls (not a
self-HTTP-loop). Each partial endpoint owns the response framing for
HTMX consumption — the headers + element IDs HTMX needs (`hx-swap`
target, polling triggers) live in the rendered Jinja partial, not
on the endpoint.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from core.api.health import health as _core_health
from core.api.stats import top_tools as _core_top_tools
from core.config import Settings, get_settings
from core.db.session import get_db


TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["ui"])


@router.get("/")
async def index(request: Request):
    """Render the operator dashboard. Task 0 ships a placeholder;
    Task 4 replaces it with the real composition (header strip +
    three stacked panels)."""
    return templates.TemplateResponse(request, "index.html")


@router.get("/partials/health-bar")
def health_bar_partial(
    request: Request,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    """Render the Health/Stats bar partial against fresh data.

    Composes `/health` + `/stats/top-tools` via direct handler calls.
    The bar itself wires the 10s HTMX poll via `hx-get` on the
    rendered element (see `templates/partials/health_bar.html`).
    """
    health_payload = _core_health(request, settings=settings, db=db)
    top_tools_response = _core_top_tools(db=db)
    return templates.TemplateResponse(
        request,
        "partials/health_bar.html",
        {
            "health": health_payload,
            "top_tools": top_tools_response.items,
        },
    )
