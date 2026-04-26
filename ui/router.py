"""UI router — operator dashboard surface.

Included by `ui.app:create_app()` onto the FastAPI app produced by
`core.app:create_app()`. Per the Day 10 alignment decision (DECISIONS
`[2026-05-01 Day 10]`), `core/` stays UI-free; this router and its
companion templates / static assets / wrapper factory live entirely
under `ui/`.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates


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
