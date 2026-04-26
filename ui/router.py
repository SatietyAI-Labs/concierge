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
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from core.api.health import health as _core_health
from core.api.stats import top_tools as _core_top_tools
from core.api.tools import list_tools as _core_list_tools
from core.config import Settings, get_settings
from core.db.models import Tool
from core.db.session import get_db
from core.lifecycle_store.schema import StatusChange
from core.lifecycle_store.service import (
    LifecycleService,
    RequestNotFoundError,
)
from core.lifecycle_store.transitions import InvalidTransitionError


def _none_if_blank(s: Optional[str]) -> Optional[str]:
    """Empty / whitespace-only filter values become None — the form
    submits `?tool_type=` when "All types" is selected, and the
    catalog filters need no-filter semantics in that case rather
    than `Tool.tool_type == ""` (matches nothing). Localized to
    the UI partial layer; doesn't change /tools API behavior."""
    if s is None:
        return None
    s = s.strip()
    return s if s else None


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


@router.get("/partials/tool-registry")
def tool_registry_partial(
    request: Request,
    pack_slug: Optional[str] = Query(None),
    tool_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    name_q: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Render the Tool Registry partial. Three-way branch:

    1. **catalog-empty** (zero total tools in DB) → designed empty
       state explaining Concierge has no tools yet.
    2. **filter-empty** (filtered count zero with non-empty catalog)
       → designed empty state telling the operator their filter
       excluded everything; offer clear/refine action.
    3. **non-empty** → cards-in-pack-groups layout grouped by
       `pack_slug`.

    Per the Day 10 alignment task-deliverable expansion: empty-state
    behavior splits between catalog-empty and filter-empty for
    distinct empty-condition UX (Real Check 1 + operator pushback).
    """
    # Filter values from the form arrive as raw strings; convert
    # empty / whitespace-only to None so the catalog filters apply
    # no-filter semantics rather than `column == ""` matching nothing.
    pack_slug = _none_if_blank(pack_slug)
    tool_type = _none_if_blank(tool_type)
    category = _none_if_blank(category)
    name_q = _none_if_blank(name_q)

    filters = {
        "pack_slug": pack_slug,
        "tool_type": tool_type,
        "category": category,
        "name_q": name_q,
    }

    # Catalog-empty branch — zero total tools regardless of filters.
    total_catalog = db.query(Tool).count()
    if total_catalog == 0:
        return templates.TemplateResponse(
            request, "partials/tool_registry_empty_catalog.html"
        )

    # Apply filters via the existing core handler. Direct call (not
    # self-HTTP-loop) — same composition pattern as the health-bar
    # partial.
    tool_list = _core_list_tools(
        pack_id=None,
        pack_slug=pack_slug,
        is_active=None,
        is_in_manifest=None,
        dormant=None,
        category=category,
        tool_type=tool_type,
        slug=None,
        name_q=name_q,
        limit=1000,  # v0.1 dashboard doesn't paginate the registry
        offset=0,
        db=db,
    )

    # Filter-empty branch — catalog has tools but the filter
    # excluded all of them.
    if tool_list.total == 0:
        return templates.TemplateResponse(
            request,
            "partials/tool_registry_empty_filter.html",
            {"filters": filters},
        )

    # Group by pack_slug for cards-in-pack-groups layout. Stable
    # ordering: pack_slug ASC, with `None` (unpacked tools) sorted
    # last under the "Unpacked" header.
    by_pack: dict[Optional[str], dict] = {}
    for tool in tool_list.items:
        key = tool.pack_slug
        if key not in by_pack:
            by_pack[key] = {
                "slug": tool.pack_slug,
                "name": tool.pack_name or "Unpacked",
                "tools": [],
            }
        by_pack[key]["tools"].append(tool)

    packs = sorted(
        by_pack.values(),
        key=lambda p: (p["slug"] is None, p["slug"] or ""),
    )

    return templates.TemplateResponse(
        request,
        "partials/tool_registry.html",
        {"packs": packs, "filters": filters},
    )


# ---- Pending Requests Inbox + actions -------------------------------


_ACTION_TO_STATUS = {
    "approve": "approved",
    "deny": "denied",
    "defer": "deferred",
}
"""UI button label → file-side StatusChange.status value. The button
labels (Approve/Deny/Defer) come from the operator's mental model;
the StatusChange status field uses the past-tense file-side
vocabulary per `core.lifecycle_store.transitions`. This mapping is
the only place the two surfaces meet."""


def _build_lifecycle_service(
    request: Request, db: Session, settings: Settings
) -> LifecycleService:
    """Construct a LifecycleService matching core/api/requests.py's
    `get_lifecycle_service` shape — same DI pattern, just inline
    rather than via FastAPI Depends, because we need the service
    inside the action-POST handler where Depends would re-resolve."""
    return LifecycleService(
        session=db,
        lifecycle_root=settings.lifecycle_root,
        event_broker=getattr(request.app.state, "event_broker", None),
    )


def _render_pending_inbox(
    request: Request, db: Session, settings: Settings
):
    """Render the pending-inbox partial against fresh list_pending
    data. Used by both the GET partial endpoint and the action POST
    handler (which returns the refreshed inbox so resolved requests
    fall out of view)."""
    service = _build_lifecycle_service(request, db, settings)
    items = service.list_pending(stale=False, limit=100, offset=0)
    return templates.TemplateResponse(
        request,
        "partials/pending_inbox.html",
        {"items": items},
    )


@router.get("/partials/pending-inbox")
def pending_inbox_partial(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Render the Pending Requests Inbox partial against current
    `list_pending` data. SSE-driven refresh on `new_request` events
    triggers this endpoint via `ui/static/js/concierge.js`; HTMX
    polling fallback wires through the same endpoint when the SSE
    stream isn't available."""
    return _render_pending_inbox(request, db, settings)


@router.post("/partials/requests/{filename}/action")
def pending_inbox_action(
    request: Request,
    filename: str,
    action: str = Form(...),
    comment: str = Form(""),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Handle Approve/Deny/Defer button submissions. Translates form
    data to a StatusChange and calls the LifecycleService directly.
    Returns the freshly-rendered inbox partial so the resolved
    request disappears from the visible list.

    Comment field maps to `conditions` for approve transitions
    (operator's approval conditions per the request schema) and to
    `notes` for deny/defer transitions (decision rationale). Both
    fields exist on StatusChange; this picks the right one for the
    action shape rather than passing the same field for everything.
    """
    if action not in _ACTION_TO_STATUS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown action {action!r} (valid: {sorted(_ACTION_TO_STATUS)})",
        )

    target_status = _ACTION_TO_STATUS[action]
    comment_clean = comment.strip() if comment else ""
    if action == "approve":
        change = StatusChange(
            status=target_status,
            conditions=comment_clean or None,
        )
    else:
        change = StatusChange(
            status=target_status,
            notes=comment_clean or None,
        )

    service = _build_lifecycle_service(request, db, settings)
    try:
        service.update_status(filename=filename, change=change)
    except RequestNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "request_not_found", "message": str(exc)},
        )
    except InvalidTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "invalid_transition", "message": str(exc)},
        )

    return _render_pending_inbox(request, db, settings)
