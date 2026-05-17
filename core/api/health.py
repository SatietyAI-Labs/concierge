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
from core.db.models import (
    ACTIVE_LIFECYCLE_STATES,
    DORMANT_LIFECYCLE_STATES,
    Pack,
    Request as RequestRow,
    Tool,
)
from core.db.session import get_db
from core.lifecycle_store.service import get_counters as get_lifecycle_counters
from core.recommend.counters import get_counters as get_recommend_counters


router = APIRouter(tags=["health"])


def _catalog_counts(db: Session) -> dict[str, int]:
    return {
        "packs": db.query(func.count(Pack.id)).scalar() or 0,
        "tools": db.query(func.count(Tool.id)).scalar() or 0,
        # "active" / "dormant" derive from `lifecycle_state` — the
        # canonical authority — since the legacy `is_active` column was
        # retired (D112). `tools_active` = loaded-on-boot; `tools_dormant`
        # = in-manifest activation candidates. See core/db/models.py.
        "tools_active": db.query(func.count(Tool.id))
        .filter(Tool.lifecycle_state.in_(ACTIVE_LIFECYCLE_STATES))
        .scalar()
        or 0,
        "tools_dormant": db.query(func.count(Tool.id))
        .filter(
            Tool.is_in_manifest.is_(True),
            Tool.lifecycle_state.in_(DORMANT_LIFECYCLE_STATES),
        )
        .scalar()
        or 0,
    }


def _requests_counts(db: Session) -> dict[str, int]:
    """Pending/resolved/archived counts for the dashboard health bar.

    `pending` mirrors the inbox query (`folder='pending' AND
    status='pending'`) so operators see the same number on the bar
    and in the inbox card list. The conjunctive filter — rather than
    the looser `status='pending'` alone — locks the alignment claim
    under both drift directions: forward (folder=pending,
    status≠pending) and reverse (status=pending, folder≠pending).

    `resolved` and `archived` remain folder-based so folder/status
    drift surfaces as a /health diagnostic signal: cron-reconciliation
    lag will show up as resolved/archived rows whose status hasn't
    caught up. Mixed semantic is deliberate, not oversight. See
    DECISIONS `[2026-05-02 Day 11]` D1.
    """
    folder_rows = (
        db.query(RequestRow.folder, func.count(RequestRow.id))
        .group_by(RequestRow.folder)
        .all()
    )
    folder_counts = {"resolved": 0, "archived": 0}
    for folder, n in folder_rows:
        if folder in folder_counts:
            folder_counts[folder] = n
    pending_count = (
        db.query(func.count(RequestRow.id))
        .filter(RequestRow.folder == "pending")
        .filter(RequestRow.status == "pending")
        .scalar()
        or 0
    )
    total = db.query(func.count(RequestRow.id)).scalar() or 0
    return {
        "pending": pending_count,
        "resolved": folder_counts["resolved"],
        "archived": folder_counts["archived"],
        "total": total,
    }


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
        requests_counts = _requests_counts(db)
    except Exception as exc:  # pragma: no cover
        requests_counts = {}
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
        "requests": requests_counts,
        "scanner": scanner_field,
    }
    if warnings:
        body["health_warnings"] = warnings
    return body
