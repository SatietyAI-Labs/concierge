"""One-shot catalog reconciliation — Stage 1B reconciliation slice, Phase B.

Applies the operator-policy transformations (master plan §III.2 item 7;
DECISIONS D40 / D79 / D77) that the Gate-2 manifest ingest deliberately
did **not** make. The ingest faithfully reflects `TOOL-MANIFEST.md` as
authored (D40 — "never weld operator policy into ingest code"); this
module is the dedicated home for the operator's reconciliation policy,
applied DB-side against the catalog rows the ingest produced.

The reconciliation — five D40 transitions + one D77 pin:

  - mailerlite                → retired, succeeded_by='ghl'
  - ghl                       → new row (MailerLite's successor)
  - stripe                    → pending-decision
  - cloudflare                → pending-decision
  - elevenlabs                → on-demand
  - semantic-memory-chromadb  → pin_status='always-pinned'

**Mechanism (D40 option d).** Lifecycle transitions go through the
validated `transition_tool_lifecycle` service path — not raw SQL. The
four transitions were confirmed legal at design time (all from
`loaded-on-boot`; see `core/tool_transitions.py`), and the validator is
a second line of defence: an unexpected pre-state surfaces as a
reported `error`, not a silent bad write. `succeeded_by` and
`pin_status` are plain column writes (neither is transition-guarded).

**Idempotency — safe to re-run.** Lifecycle transitions self-no-op when
the row is already at the target state (`transition_tool_lifecycle`
returns early on `old == new`); the GHL insert is guarded by a slug
lookup; `succeeded_by` / `pin_status` writes are value-equal on a
re-run. A second run reports every operation `already_satisfied` and
writes nothing.

**Commit boundary.** `reconcile_catalog()` flushes but does not commit —
the caller (`scripts/reconcile_catalog.py`) owns the commit so the run
is observably all-or-nothing (and `--dry-run` is a plain rollback).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from core.db.models import Tool
from core.tool_transitions import (
    IllegalLifecycleTransition,
    transition_tool_lifecycle,
)


log = logging.getLogger("concierge.catalog_reconcile")


# ---- The reconciliation spec (DECISIONS D40 / D79 / D77) ----------------


@dataclass(frozen=True)
class LifecycleOp:
    """One D40 lifecycle transition, optionally pairing a
    `succeeded_by` write (the MailerLite → GHL retirement lineage)."""

    slug: str
    target_state: str
    succeeded_by: str | None = None


# The four D40 lifecycle transitions. Order is not load-bearing
# (`succeeded_by` is a plain slug, not a foreign key) — it reads
# top-to-bottom as the operator-policy narrative.
LIFECYCLE_OPS: tuple[LifecycleOp, ...] = (
    LifecycleOp("mailerlite", "retired", succeeded_by="ghl"),
    LifecycleOp("stripe", "pending-decision"),
    LifecycleOp("cloudflare", "pending-decision"),
    LifecycleOp("elevenlabs", "on-demand"),
)

# The D77 pin: Alfred's semantic-memory MCP — the canonical
# `always-pinned` case (a tool whose value is invisible to usage
# telemetry, so the autonomous scanner would otherwise flag it for
# demotion every pass).
PIN_OPS: tuple[tuple[str, str], ...] = (
    ("semantic-memory-chromadb", "always-pinned"),
)

# The GHL row — MailerLite's successor. GHL is absent from
# `TOOL-MANIFEST.md` (adding it to the manifest is a separate operator
# step, D40), hence `is_in_manifest=False`. Created at `loaded-on-boot`
# (D40: GHL "active"; the ingest's `ACTIVE → loaded-on-boot` mapping).
# `pin_status` is left to the model default (`auto-managed`) — GHL is
# Concierge-managed, the canonical `auto-managed` successor case (D77).
GHL_ROW: dict[str, object] = {
    "slug": "ghl",
    "name": "GHL",
    "description": (
        "GoHighLevel CRM and marketing-automation MCP — the fleet's "
        "email / marketing capability; MailerLite's successor."
    ),
    "tool_type": "mcp",
    "lifecycle_state": "loaded-on-boot",
    "is_active": True,
    "is_in_manifest": False,
}


# ---- Result reporting ---------------------------------------------------

# Per-operation outcome vocabulary (internal to this module + its test):
#   applied           — a write happened this run
#   already_satisfied — nothing to do (the row is already reconciled —
#                       an idempotent re-run, or a partial-run recovery)
#   skipped_missing   — the target slug is not in the catalog
#   error             — the operation could not be applied (e.g. an
#                       illegal lifecycle transition from an unexpected
#                       pre-state); `detail` carries the reason
_OK_OUTCOMES = frozenset({"applied", "already_satisfied"})


@dataclass
class OpResult:
    slug: str
    kind: str       # "transition" | "insert" | "pin"
    outcome: str
    detail: str = ""


@dataclass
class ReconcileSummary:
    results: list[OpResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when every operation either applied cleanly or was
        already satisfied — i.e. nothing was missing or errored."""
        return all(r.outcome in _OK_OUTCOMES for r in self.results)

    def count(self, outcome: str) -> int:
        return sum(1 for r in self.results if r.outcome == outcome)


# ---- Public entrypoint --------------------------------------------------


def reconcile_catalog(session: Session) -> ReconcileSummary:
    """Apply the catalog reconciliation against `session`'s DB.

    Flushes each write but does NOT commit — the caller owns the commit
    boundary. Returns a `ReconcileSummary` with one `OpResult` per
    operation (the GHL insert, the four lifecycle transitions, the pin).
    """
    summary = ReconcileSummary()
    log.info("catalog_reconcile.started")

    # 1. The GHL row first — the successor exists before MailerLite's
    #    `succeeded_by` points at it (informational, not an FK, but it
    #    reads honestly in that order).
    _reconcile_ghl_insert(session, summary)

    # 2. The four D40 lifecycle transitions.
    for op in LIFECYCLE_OPS:
        _reconcile_lifecycle(session, op, summary)

    # 3. The D77 pin(s).
    for slug, pin_status in PIN_OPS:
        _reconcile_pin(session, slug, pin_status, summary)

    log.info(
        "catalog_reconcile.finished applied=%d already_satisfied=%d "
        "skipped_missing=%d error=%d",
        summary.count("applied"),
        summary.count("already_satisfied"),
        summary.count("skipped_missing"),
        summary.count("error"),
    )
    return summary


# ---- Per-operation helpers ----------------------------------------------


def _reconcile_ghl_insert(session: Session, summary: ReconcileSummary) -> None:
    """Insert the GHL catalog row. Idempotent — guarded by a slug
    lookup, so a re-run finds the existing row and writes nothing."""
    slug = str(GHL_ROW["slug"])
    existing = session.query(Tool).filter_by(slug=slug).one_or_none()
    if existing is not None:
        summary.results.append(
            OpResult(slug, "insert", "already_satisfied",
                     "GHL row already present")
        )
        return
    tool = Tool(**GHL_ROW)
    session.add(tool)
    session.flush()
    log.info("catalog_reconcile.ghl_inserted slug=%s id=%s", slug, tool.id)
    summary.results.append(
        OpResult(slug, "insert", "applied",
                 "GHL row created (loaded-on-boot, is_in_manifest=False)")
    )


def _reconcile_lifecycle(
    session: Session, op: LifecycleOp, summary: ReconcileSummary
) -> None:
    """Apply one lifecycle transition (+ optional `succeeded_by`).

    The transition goes through `transition_tool_lifecycle`, so an
    illegal transition from an unexpected pre-state raises and is
    reported as `error` rather than silently mis-writing. A re-run
    self-no-ops (the row is already at the target)."""
    tool = session.query(Tool).filter_by(slug=op.slug).one_or_none()
    if tool is None:
        summary.results.append(
            OpResult(op.slug, "transition", "skipped_missing",
                     f"slug {op.slug!r} not in catalog")
        )
        return

    old_state = tool.lifecycle_state
    old_succeeded_by = tool.succeeded_by
    try:
        transition_tool_lifecycle(session, tool, op.target_state)
    except IllegalLifecycleTransition as exc:
        summary.results.append(
            OpResult(op.slug, "transition", "error",
                     f"illegal transition {old_state!r}→"
                     f"{op.target_state!r}: {exc}")
        )
        return

    if op.succeeded_by is not None and tool.succeeded_by != op.succeeded_by:
        tool.succeeded_by = op.succeeded_by
        session.flush()

    changed = (
        old_state != tool.lifecycle_state
        or old_succeeded_by != tool.succeeded_by
    )
    detail = f"lifecycle_state {old_state}→{tool.lifecycle_state}"
    if op.succeeded_by is not None:
        detail += f", succeeded_by={tool.succeeded_by}"
    summary.results.append(
        OpResult(
            op.slug, "transition",
            "applied" if changed else "already_satisfied",
            detail,
        )
    )


def _reconcile_pin(
    session: Session, slug: str, pin_status: str, summary: ReconcileSummary
) -> None:
    """Set a tool's `pin_status`. Idempotent — value-equal on a re-run."""
    tool = session.query(Tool).filter_by(slug=slug).one_or_none()
    if tool is None:
        summary.results.append(
            OpResult(slug, "pin", "skipped_missing",
                     f"slug {slug!r} not in catalog")
        )
        return
    if tool.pin_status == pin_status:
        summary.results.append(
            OpResult(slug, "pin", "already_satisfied",
                     f"pin_status already {pin_status}")
        )
        return
    old = tool.pin_status
    tool.pin_status = pin_status
    session.flush()
    log.info(
        "catalog_reconcile.pin_set slug=%s %s->%s", slug, old, pin_status
    )
    summary.results.append(
        OpResult(slug, "pin", "applied", f"pin_status {old}→{pin_status}")
    )


__all__ = [
    "LifecycleOp",
    "LIFECYCLE_OPS",
    "PIN_OPS",
    "GHL_ROW",
    "OpResult",
    "ReconcileSummary",
    "reconcile_catalog",
]
