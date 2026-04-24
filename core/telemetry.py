"""Per-tool telemetry emit helpers — writes `ToolUsageEvent` rows.

Per blueprint-v2 §D audit + DECISIONS `[2026-04-23]` (C7 scanner in v1),
the promotion/demotion scanner aggregates over `ToolUsageEvent` rows to
produce weekly-review signal. This module is the write-side counterpart
to that: a thin helper that resolves a Tool by slug and inserts a usage
event with the correct event_type + optional context.

Callable sites (Fix Day 3 Task 2):

- `core/recommend/service.py::recommend` — emits one
  `event_type='recommended'` event per in-catalog recommendation
- `core/lifecycle_store/service.py::_maybe_install_on_approve` — emits
  `event_type='installed'` on successful install
- `adapters/claude_code/backing_server_registry.py::load` — emits
  `event_type='loaded'` when a backing server is loaded into a Claude
  Code session

**Session-id propagation is deliberately deferred.** Per Fix Day 3
Fork 2, `session_id=None` is the correct shape today — partial
population (loader sets session_id, recommend leaves null) would imply
the field means something it doesn't yet. Fix Day 4's narration-as-push
work touches the same three surfaces; real session-id propagation lands
there as a coordinated change.

**Missing-slug policy:** when `emit_usage_event` is called with a slug
that isn't in the catalog (e.g. a discovery recommendation where the
tool doesn't yet exist), the helper logs WARNING and returns silently.
Callers don't have to pre-check. The WARN surfaces if a code path is
emitting with bad data; production should never see it for recommend
(those recs have `tool_slug` populated only for in-catalog rows) or
install (which targets a known slug by construction).
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from core.db.models import Tool, ToolUsageEvent, USAGE_EVENT_TYPE_VALUES


log = logging.getLogger("concierge.telemetry")


UsageEventSink = Callable[[str, str, Optional[dict[str, Any]]], None]
"""Injectable sink signature for telemetry emits.

Signature: `(tool_slug, event_type, context) -> None`. `session_id`
is intentionally NOT in the signature per Fix Day 3 Fork 2 — leaving
it null uniformly until Fix Day 4 wires real session-id propagation
across all three emit sites. When that happens this signature
extends with a `session_id: Optional[str] = None` kwarg.
"""


def noop_sink(
    tool_slug: str, event_type: str, context: Optional[dict[str, Any]] = None
) -> None:
    """Default sink — accepts and drops. Used by tests and by
    RecommendationService when no DB-backed sink is wired.
    """


def make_db_sink(session: Session) -> UsageEventSink:
    """Build a sink that writes `ToolUsageEvent` rows into `session`.

    The returned closure captures the Session. FastAPI owns the session
    lifetime via `get_db`; the closure is only ever invoked inside the
    request handler where the session is live. Don't build a sink
    outside of a request scope — the session would be closed before
    the closure fires.
    """

    def sink(
        tool_slug: str,
        event_type: str,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        emit_usage_event(
            session,
            tool_slug=tool_slug,
            event_type=event_type,
            context=context,
        )

    return sink


def emit_usage_event(
    session: Session,
    *,
    tool_slug: str,
    event_type: str,
    context: Optional[dict[str, Any]] = None,
    session_id: Optional[str] = None,
) -> Optional[ToolUsageEvent]:
    """Insert a `ToolUsageEvent` row for the given `tool_slug`.

    Returns the inserted row on success, or `None` if the tool slug
    was not found in the catalog (logged at WARNING). Raises
    `ValueError` on unknown `event_type` — the enum is authoritative
    and silently accepting bad event types would break the scanner's
    aggregation assumptions.

    The caller owns the transaction: this helper adds + flushes but
    does not commit. Commit boundaries stay with the service /
    endpoint layer that owns the Session.
    """
    if event_type not in USAGE_EVENT_TYPE_VALUES:
        raise ValueError(
            f"unknown event_type {event_type!r} "
            f"(valid: {sorted(USAGE_EVENT_TYPE_VALUES)})"
        )

    tool = session.query(Tool).filter_by(slug=tool_slug).one_or_none()
    if tool is None:
        log.warning(
            "telemetry.slug_not_found slug=%s event_type=%s",
            tool_slug, event_type,
        )
        return None

    evt = ToolUsageEvent(
        tool_id=tool.id,
        event_type=event_type,
        session_id=session_id,
        context=context,
    )
    session.add(evt)
    session.flush()
    log.debug(
        "telemetry.emit slug=%s event_type=%s tool_id=%s",
        tool_slug, event_type, tool.id,
    )
    return evt
