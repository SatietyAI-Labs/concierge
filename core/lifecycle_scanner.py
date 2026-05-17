"""Promotion / demotion / stale-pending scanner.

Fix Day 4 Task 5 — §C7 per DECISIONS `[2026-04-23]`. Weekly-review
automation: aggregates over `tool_usage_events` to produce
promotion candidates, demotion candidates, and flags stale-pending
requests.

## What this does

One `run_once(session, *, memory=None, broker=None)` pass:

1. **Promotion candidates** — tools with ≥ `PROMOTION_MIN_USES`
   (5) events of type `recommended` / `loaded` / `used` in the
   last `PROMOTION_WINDOW_DAYS` (30) days.
   - **Auto-promote** if install age ≥ 30 days AND not already
     `loaded-on-boot` AND not `retired` AND not `on-demand`. The
     scanner calls `transition_tool_lifecycle` with the
     `refresh_identity_on_loaded_on_boot_change` hook so identity
     refresh fires automatically (Fix Day 3 Fork 5 wiring).
   - **Flag as ambiguous** if install age < 30 days (too fresh —
     per Fork G, the 30-day threshold keeps the scanner from
     over-promoting newly-installed tools that happened to get a
     burst of recommendations).
   - **Skip** if already `loaded-on-boot` (idempotent re-runs).
   - **Skip** if `retired` (only path out of retired is
     `retired → discovered` per lifecycle transitions table).
   - **Skip** if `on-demand`. `on-demand` is a *settled* operator
     decision — the tool is deliberately kept off the boot context
     budget. Autonomous promotion would silently undo that decision,
     so the scanner never auto-promotes an `on-demand` tool.
     `on-demand → loaded-on-boot` remains a legal *manual*
     transition; only the autonomous path is skipped.

2. **Demotion candidates** — tools in state `loaded-on-boot` whose
   most recent `tool_usage_events.timestamp` is older than
   `DEMOTION_INACTIVITY_DAYS` (90) days (or no events at all). Per
   close-the-gap plan's Fork F, flag-only; no auto-demote. Operator
   reviews and manually transitions if appropriate.
   - **`always-pinned` tools are exempt** (D77 operator-pin
     authority): a tool the operator has pinned to `loaded-on-boot`
     is never flagged for demotion, regardless of usage telemetry.
     Pinned tools are typically the ones whose value is invisible to
     usage counters (e.g. a semantic-memory MCP) — exactly the rows
     the inactivity heuristic would otherwise mis-flag every pass.

3. **Stale pending** — `requests` rows in folder `pending` with
   `created_at` older than `STALE_PENDING_DAYS` (7) days.

Returns a `ScannerSummary` with the three sets + `auto_promoted`
(tools actually transitioned this pass) + `ran_at` timestamp +
any non-fatal errors encountered.

## What this does NOT do

- **No automatic demotion.** Per close-the-gap plan — demotion is
  always operator-reviewed, to avoid silently removing tools from
  the toolbelt.
- **No persistence of candidate queue.** Per Fork F, candidates
  are ephemeral per scan run. `/health` surfaces the latest
  summary; operator re-runs to re-surface.
- **No skills-specific "used" detection.** Per Fork H (deferred).
  Today's scanner aggregates over whatever `tool_usage_events`
  rows exist; for skills that means primarily `recommended`
  events until a skills-usage emit path is built.

## How it wires into the app

- Registered as a weekly APScheduler job in `core/app.py`'s
  lifespan (Sunday 03:00 local, matching operator weekly-review
  cadence — see `_register_weekly_job`).
- Manual trigger via `POST /scanner/run` (see
  `core/api/scanner.py`) for operator on-demand re-scans.
- Last summary stored on `app.state.last_scanner_summary` (per
  Fork F — ephemeral, not persisted to DB) so `/health` can
  surface counts without re-running.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.db.models import Request, Tool, ToolUsageEvent
from core.identity import refresh_identity_on_loaded_on_boot_change
from core.lifecycle_policy import (
    DEMOTION_INACTIVITY_DAYS,
    PROMOTION_MIN_USES,
    PROMOTION_WINDOW_DAYS,
    STALE_PENDING_DAYS,
)
from core.tool_transitions import (
    IllegalLifecycleTransition,
    transition_tool_lifecycle,
)


log = logging.getLogger("concierge.scanner")


# Fork G: install-age minimum for auto-promotion. 30 days prevents
# newly-installed tools from auto-promoting on a burst of initial
# recommendations — sustained-usage signal requires time.
AUTO_PROMOTE_MIN_INSTALL_AGE_DAYS: int = 30


# Events that count toward "usage" for promotion. Admin events
# (`installed`, `removed`) are excluded — they're one-shot lifecycle
# markers, not signal that the tool is being actively exercised.
PROMOTION_SIGNAL_EVENT_TYPES: tuple[str, ...] = (
    "recommended",
    "loaded",
    "used",
)


@dataclass(frozen=True)
class PromotionCandidate:
    slug: str
    event_count: int
    window_days: int
    install_age_days: Optional[int]
    current_state: str
    reason: str  # "auto_promoted" | "install_age_below_threshold" | "retired_cannot_promote" | "already_loaded_on_boot" | "on_demand_settled"


@dataclass(frozen=True)
class DemotionCandidate:
    slug: str
    last_event_at: Optional[datetime]
    inactivity_days: int  # days since last event; -1 when never had an event


@dataclass(frozen=True)
class StalePendingRequest:
    filename: str
    folder: str
    age_days: int


@dataclass
class ScannerSummary:
    """One scan run's output.

    `auto_promoted` is a subset of `promotion_candidates` — the
    slugs whose lifecycle_state was actually transitioned by this
    run. Ambiguous candidates appear in `promotion_candidates` with
    a non-"auto_promoted" reason and are NOT in `auto_promoted`.
    """

    ran_at: datetime
    promotion_candidates: list[PromotionCandidate] = field(default_factory=list)
    auto_promoted: list[str] = field(default_factory=list)
    demotion_candidates: list[DemotionCandidate] = field(default_factory=list)
    stale_pending: list[StalePendingRequest] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_health_dict(self) -> dict:
        """Shape consumed by `/health`'s scanner field. Counts +
        slugs (not full objects) so the payload stays small. Empty
        lists when no candidates — operator sees the run happened.
        """
        return {
            "last_ran_at": self.ran_at.isoformat(),
            "auto_promoted_count": len(self.auto_promoted),
            "auto_promoted_slugs": list(self.auto_promoted),
            "promotion_candidates_count": len(self.promotion_candidates),
            "promotion_candidates_slugs": [
                c.slug for c in self.promotion_candidates
            ],
            "demotion_candidates_count": len(self.demotion_candidates),
            "demotion_candidates_slugs": [
                c.slug for c in self.demotion_candidates
            ],
            "stale_pending_count": len(self.stale_pending),
            "stale_pending_filenames": [
                s.filename for s in self.stale_pending
            ],
            "errors": list(self.errors),
        }


# ---- Public entrypoint --------------------------------------------------


def run_once(
    session: Session,
    *,
    memory=None,
    now: Optional[datetime] = None,
) -> ScannerSummary:
    """Execute one scanner pass.

    `session` is an open SQLAlchemy session; caller owns the commit
    boundary (auto-promote transitions flush but do not commit, so
    an exception rolls back the full pass).

    `memory` is an optional `MemoryClient` passed to the identity-
    refresh hook. When None, auto-promotions still fire but
    identity refresh is silently skipped — matches Fix Day 3's
    graceful-degradation posture when memory is unavailable.

    `now` is injectable for deterministic testing. Defaults to
    `datetime.now(timezone.utc)`.

    Commits: this function FLUSHES but does not COMMIT. The caller
    (scheduler job, manual-trigger endpoint) owns the final commit
    so a partial run is observably all-or-nothing.
    """
    now = now or datetime.now(timezone.utc)
    ran_at = now
    summary = ScannerSummary(ran_at=ran_at)
    log.info("scanner.run_once_started at=%s", ran_at.isoformat())

    try:
        _collect_promotions(session, summary=summary, now=now, memory=memory)
    except Exception as exc:
        log.exception("scanner.promotion_pass_failed: %s", exc)
        summary.errors.append(f"promotion_pass: {type(exc).__name__}: {exc}")

    try:
        _collect_demotions(session, summary=summary, now=now)
    except Exception as exc:
        log.exception("scanner.demotion_pass_failed: %s", exc)
        summary.errors.append(f"demotion_pass: {type(exc).__name__}: {exc}")

    try:
        _collect_stale_pending(session, summary=summary, now=now)
    except Exception as exc:
        log.exception("scanner.stale_pending_pass_failed: %s", exc)
        summary.errors.append(
            f"stale_pending_pass: {type(exc).__name__}: {exc}"
        )

    log.info(
        "scanner.run_once_completed auto_promoted=%d promotion_candidates=%d "
        "demotion_candidates=%d stale_pending=%d errors=%d",
        len(summary.auto_promoted),
        len(summary.promotion_candidates),
        len(summary.demotion_candidates),
        len(summary.stale_pending),
        len(summary.errors),
    )
    return summary


# ---- Promotion ----------------------------------------------------------


def _collect_promotions(
    session: Session,
    *,
    summary: ScannerSummary,
    now: datetime,
    memory,
) -> None:
    """Aggregate promotion-signal events per tool over the window.
    Each tool meeting the event threshold lands in
    `promotion_candidates` with a classification reason; the ones
    classified `auto_promoted` also get their state transitioned
    via `transition_tool_lifecycle`.
    """
    window_start = now - timedelta(days=PROMOTION_WINDOW_DAYS)

    rows = (
        session.query(
            Tool.id,
            Tool.slug,
            Tool.lifecycle_state,
            Tool.created_at,
            func.count(ToolUsageEvent.id).label("event_count"),
        )
        .join(ToolUsageEvent, ToolUsageEvent.tool_id == Tool.id)
        .filter(ToolUsageEvent.timestamp >= window_start)
        .filter(ToolUsageEvent.event_type.in_(PROMOTION_SIGNAL_EVENT_TYPES))
        .group_by(Tool.id)
        .having(func.count(ToolUsageEvent.id) >= PROMOTION_MIN_USES)
        .all()
    )

    for tool_id, slug, current_state, created_at, event_count in rows:
        install_age_days = _install_age_days(created_at, now)
        reason, should_promote = _classify_promotion(
            current_state=current_state,
            install_age_days=install_age_days,
        )
        summary.promotion_candidates.append(
            PromotionCandidate(
                slug=slug,
                event_count=event_count,
                window_days=PROMOTION_WINDOW_DAYS,
                install_age_days=install_age_days,
                current_state=current_state,
                reason=reason,
            )
        )
        if should_promote:
            tool = session.get(Tool, tool_id)
            if tool is None:  # defensive — row vanished mid-pass
                log.warning(
                    "scanner.promote_skipped_tool_gone slug=%s", slug
                )
                continue
            try:
                transition_tool_lifecycle(
                    session,
                    tool,
                    "loaded-on-boot",
                    on_transition=(
                        (lambda t, old, new, s=session, m=memory:
                         refresh_identity_on_loaded_on_boot_change(
                             t, old, new, session=s, memory=m,
                         ))
                        if memory is not None
                        else None
                    ),
                )
                summary.auto_promoted.append(slug)
                log.info(
                    "scanner.auto_promoted slug=%s event_count=%d "
                    "install_age_days=%s old_state=%s new_state=loaded-on-boot",
                    slug, event_count, install_age_days, current_state,
                )
            except IllegalLifecycleTransition as exc:
                # Shouldn't happen given the classification above,
                # but defense-in-depth: log + treat as ambiguous.
                log.warning(
                    "scanner.promote_rejected_illegal slug=%s "
                    "old_state=%s reason=%s",
                    slug, current_state, exc,
                )
                summary.errors.append(
                    f"promote_rejected_illegal:{slug}:{exc}"
                )


def _classify_promotion(
    *, current_state: str, install_age_days: Optional[int]
) -> tuple[str, bool]:
    """Return (reason, should_auto_promote) for a tool meeting the
    event-count threshold. Reason codes mirror the module-docstring
    enumeration.
    """
    if current_state == "loaded-on-boot":
        return ("already_loaded_on_boot", False)
    if current_state == "retired":
        return ("retired_cannot_promote", False)
    if current_state == "on-demand":
        # `on-demand` is a settled "keep it, but not at boot" operator
        # decision. Autonomous promotion would silently undo it, so the
        # scanner never auto-promotes an `on-demand` tool. The tool
        # still surfaces as a promotion *candidate* (the operator can
        # manually promote via `on-demand → loaded-on-boot`, a legal
        # transition) — only the autonomous transition is skipped.
        return ("on_demand_settled", False)
    if install_age_days is None or install_age_days < AUTO_PROMOTE_MIN_INSTALL_AGE_DAYS:
        return ("install_age_below_threshold", False)
    return ("auto_promoted", True)


def _install_age_days(created_at: Optional[datetime], now: datetime) -> Optional[int]:
    """Days between the tool's catalog row creation and `now`. The
    tool's `created_at` is a proxy for install age — a per-tool
    'installed' event timestamp would be more authoritative but
    that table is still sparse (Fix Day 3 wired installs only via
    approve; operator-bootstrapped tools have no install event).

    Returns None if `created_at` is None (shouldn't happen with the
    `server_default=now()` column, but defensive).
    """
    if created_at is None:
        return None
    # created_at may be naive (SQLite returns naive datetimes for
    # server_default=func.now()). Normalize to UTC-aware so the
    # subtract is valid regardless of tz backend.
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    delta = now - created_at
    return max(0, delta.days)


# ---- Demotion -----------------------------------------------------------


def _collect_demotions(
    session: Session, *, summary: ScannerSummary, now: datetime
) -> None:
    """Flag tools in `loaded-on-boot` whose most recent usage event
    is older than `DEMOTION_INACTIVITY_DAYS` — or tools that never
    had an event at all.

    `always-pinned` tools are exempt (D77): the operator has pinned
    them to `loaded-on-boot`, so the autonomous scanner must not flag
    them for demotion regardless of usage telemetry. The exemption is
    a `pin_status != 'always-pinned'` filter on the candidate query —
    pinned rows never enter the candidate set.
    """
    inactivity_cutoff = now - timedelta(days=DEMOTION_INACTIVITY_DAYS)

    last_event_subq = (
        session.query(
            ToolUsageEvent.tool_id,
            func.max(ToolUsageEvent.timestamp).label("last_event_at"),
        )
        .group_by(ToolUsageEvent.tool_id)
        .subquery()
    )

    rows = (
        session.query(Tool.slug, last_event_subq.c.last_event_at)
        .outerjoin(last_event_subq, last_event_subq.c.tool_id == Tool.id)
        .filter(Tool.lifecycle_state == "loaded-on-boot")
        # D77 — `always-pinned` tools are exempt from autonomous
        # demotion. `pin_status` is NOT NULL, so this excludes nothing
        # spuriously: every row is `always-pinned` or `auto-managed`.
        .filter(Tool.pin_status != "always-pinned")
        .all()
    )

    for slug, last_event_at in rows:
        if last_event_at is None:
            # Tool is loaded-on-boot but has zero usage events ever.
            # Flag with sentinel -1 inactivity so operator sees the
            # "never exercised" case distinct from the "went quiet"
            # case.
            summary.demotion_candidates.append(
                DemotionCandidate(
                    slug=slug,
                    last_event_at=None,
                    inactivity_days=-1,
                )
            )
            continue
        if last_event_at.tzinfo is None:
            last_event_at = last_event_at.replace(tzinfo=timezone.utc)
        if last_event_at >= inactivity_cutoff:
            continue  # still active enough
        inactivity_days = (now - last_event_at).days
        summary.demotion_candidates.append(
            DemotionCandidate(
                slug=slug,
                last_event_at=last_event_at,
                inactivity_days=inactivity_days,
            )
        )


# ---- Stale pending ------------------------------------------------------


def _collect_stale_pending(
    session: Session, *, summary: ScannerSummary, now: datetime
) -> None:
    """`requests` rows still in folder=pending older than
    `STALE_PENDING_DAYS`.
    """
    cutoff = now - timedelta(days=STALE_PENDING_DAYS)
    rows = (
        session.query(Request)
        .filter(Request.folder == "pending")
        .filter(Request.created_at < cutoff)
        .all()
    )
    for row in rows:
        created_at = row.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        age_days = (now - created_at).days
        summary.stale_pending.append(
            StalePendingRequest(
                filename=row.filename,
                folder=row.folder,
                age_days=age_days,
            )
        )


__all__ = [
    "AUTO_PROMOTE_MIN_INSTALL_AGE_DAYS",
    "PROMOTION_SIGNAL_EVENT_TYPES",
    "PromotionCandidate",
    "DemotionCandidate",
    "StalePendingRequest",
    "ScannerSummary",
    "run_once",
]
