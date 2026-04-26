"""UI application factory — wraps the core service with the operator
dashboard surface.

Composition pattern (per DECISIONS `[2026-05-01 Day 10]`):

    headless deployments  →  core.app.create_app()
    dashboard deployments  →  ui.app.create_app()

`ui.app.create_app()` calls `core.app.create_app()` first, then
augments the resulting app with:

- The UI router (`ui.router.router`) — currently `GET /` for the
  dashboard index; partial-render endpoints layer on in Tasks 1-3
- StaticFiles mount at `/static` serving `ui/static/` (vendored
  HTMX + Pico.css under `ui/static/vendor/`; custom CSS under
  `ui/static/css/` from Task 4)

## Factory-only

This module exposes the `create_app()` factory ONLY. There is
intentionally no module-level `app = create_app()` instantiation,
matching the same pattern applied to `core.app` (per the Day 10
mid-Task-0 refactor). Factory-only keeps test fixtures clean,
avoids duplicate FastAPI instances when `ui.app` imports
`core.app`, and enables future configuration-override flexibility.

The canonical launch command is:

    uvicorn ui.app:create_app --factory --reload --port 8000

Tests construct the app via `ui.app.create_app()` directly and
control lifespan via TestClient context managers.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from core.app import create_app as create_core_app
from ui.router import STATIC_DIR, router as ui_router


def create_app() -> FastAPI:
    """Build the dashboard-augmented FastAPI app."""
    app = create_core_app()
    app.include_router(ui_router)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    return app
