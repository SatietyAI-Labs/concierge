"""GET /health — operational pulse for soak diagnostics.

This is not a liveness-only probe. Under operational-first
(DECISIONS `[2026-04-21 18:00]`), the 48h-shakedown operator needs
a single `curl | jq` surface that answers:

- Is the service alive?
- Which model is pinned? (Floating alias caught the first time.)
- How much has it served? (Request counts, token totals.)
- How many failures? (Memory outages, parse failures, invalid
  transitions — split by subsystem.)
- How big is the catalog? (Drift detection against the
  sample-catalog-state.json baseline.)
- Where is the lifecycle store? The memory store? (Isolated
  default vs. shared override readable at a glance.)

The Day-4 N18 Health/Stats bar tiles project from this endpoint;
N8 seeds the payload shape so N18 is a rendering concern, not a
data-modeling concern.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.config import Settings, get_settings
from core.db.models import Pack, Request as RequestRow, Tool
from core.db.session import get_db
from core.lifecycle_store.service import get_counters as get_lifecycle_counters
from core.recommend.counters import get_counters as get_recommend_counters


router = APIRouter(tags=["health"])


def _catalog_counts(db: Session) -> dict[str, int]:
    return {
        "packs": db.query(func.count(Pack.id)).scalar() or 0,
        "tools": db.query(func.count(Tool.id)).scalar() or 0,
        "tools_active": db.query(func.count(Tool.id))
        .filter(Tool.is_active.is_(True))
        .scalar()
        or 0,
        "tools_dormant": db.query(func.count(Tool.id))
        .filter(Tool.is_in_manifest.is_(True), Tool.is_active.is_(False))
        .scalar()
        or 0,
    }


def _requests_counts_by_folder(db: Session) -> dict[str, int]:
    rows = (
        db.query(RequestRow.folder, func.count(RequestRow.id)).group_by(RequestRow.folder).all()
    )
    counts = {"pending": 0, "resolved": 0, "archived": 0}
    for folder, n in rows:
        counts[folder] = n
    counts["total"] = sum(counts.values())
    return counts


@router.get("/health")
def health(
    request: Request,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Operational pulse — one endpoint covers liveness + config echo
    + subsystem counters + catalog counts + lifecycle row counts.

    Never 500s on a subsystem-counter read error (defense in depth:
    the health check must not itself be a new failure mode). On
    counter read failure, the field is omitted with a sentinel
    in `health_warnings` so the operator sees the partial read.
    """
    warnings: list[str] = []
    try:
        recommend_snap = get_recommend_counters().snapshot()
    except Exception as exc:  # pragma: no cover — defensive
        recommend_snap = {}
        warnings.append(f"recommend_counters_unavailable: {exc}")
    try:
        lifecycle_snap = get_lifecycle_counters().snapshot()
    except Exception as exc:  # pragma: no cover
        lifecycle_snap = {}
        warnings.append(f"lifecycle_counters_unavailable: {exc}")
    try:
        catalog = _catalog_counts(db)
    except Exception as exc:  # pragma: no cover
        catalog = {}
        warnings.append(f"catalog_counts_unavailable: {exc}")
    try:
        requests_by_folder = _requests_counts_by_folder(db)
    except Exception as exc:  # pragma: no cover
        requests_by_folder = {}
        warnings.append(f"requests_counts_unavailable: {exc}")

    # Fix Day 4 Task 5 — scanner summary field. `None` when no scan
    # has run yet (fresh process); dict shape otherwise. Per Fork F,
    # summary is in-memory (app.state), not persisted to DB, so a
    # restart clears it until the next scan run.
    last_summary = getattr(request.app.state, "last_scanner_summary", None)
    scanner_field: Any = (
        last_summary.to_health_dict() if last_summary is not None else None
    )

    body: dict[str, Any] = {
        "status": "ok",
        "env": settings.env,
        "version": "0.1.0",
        "config": {
            "model": settings.anthropic_model,
            "effort": settings.claude_code_recommend_effort,
            "memory_dir": str(settings.memory_dir),
            "lifecycle_root": str(settings.lifecycle_root),
            "database_path": str(settings.database_path),
        },
        "counters": {
            "recommend": recommend_snap,
            "lifecycle": lifecycle_snap,
        },
        "catalog": catalog,
        "requests": requests_by_folder,
        "scanner": scanner_field,
    }
    if warnings:
        body["health_warnings"] = warnings
    return body
