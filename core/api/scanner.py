"""POST /scanner/run — manual trigger for the promotion/demotion scanner.

Fix Day 4 Task 5, Fork E. Operator + demo surface for on-demand
scans; the weekly APScheduler job runs independently on its own
cadence (see `core/app.py` lifespan).

Authless by design for v1 — local-only deployment, no hostile
network surface. When the UI eventually lands on a shared host,
this endpoint grows an auth check before exposure.

The endpoint persists the resulting `ScannerSummary` on
`app.state.last_scanner_summary` so `/health` can surface counts
without re-running. Per Fork F (ephemeral-per-run): each new scan
replaces the prior summary; no history table.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from core.db.session import get_db
from core.lifecycle_scanner import ScannerSummary, run_once


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scanner", tags=["scanner"])


def _get_memory(request: Request):
    """Resolve the app-level MemoryClient for identity refresh.

    Defensive: when memory hasn't been attached to app.state (older
    test harness, lifespan skip), returns None and the scanner's
    identity refresh silently no-ops.
    """
    return getattr(request.app.state, "memory", None)


@router.post("/run")
def scanner_run(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Run one scan pass. Writes any auto-promotion transitions,
    then commits. Returns the summary as a JSON dict suitable for
    operator inspection.

    Also updates `app.state.last_scanner_summary` so `/health`
    reflects the latest state.
    """
    memory = _get_memory(request)
    summary = run_once(db, memory=memory)
    # Scanner flushes but does not commit — commit here so the
    # auto-promoted lifecycle_state changes land.
    db.commit()
    request.app.state.last_scanner_summary = summary
    logger.info(
        "scanner.manual_run_complete auto_promoted=%d promotion_candidates=%d "
        "demotion_candidates=%d stale_pending=%d",
        len(summary.auto_promoted),
        len(summary.promotion_candidates),
        len(summary.demotion_candidates),
        len(summary.stale_pending),
    )
    return summary.to_health_dict()


__all__ = ["router"]
