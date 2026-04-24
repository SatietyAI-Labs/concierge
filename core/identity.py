"""Identity-notes composition + post-transition refresh hook.

Per DECISIONS `[2026-04-23]` (Identity Notes included in v1) + Fix Day 3
Fork 5 ruling, identity notes update on ANY `Tool.lifecycle_state`
transition into OR out of `loaded-on-boot`. Explicitly includes the
`loaded-on-boot → retired` direction — losing a tool from the toolbelt
is identity-relevant signal in the same way as gaining one.

The identity note is a compact human-readable summary of the current
loaded-on-boot tool set. It injects into the recommend prompt between
the adapter preamble and X3 via `compose_recommendation_prompt`'s
`identity` parameter, giving Opus persistent operator context without
re-deriving preferences from memory search on every call.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from core.db.models import Tool
from core.memory import MemoryClient


log = logging.getLogger("concierge.identity")


def compose_identity_summary(session: Session) -> str:
    """Build the identity text from the current DB state.

    Deterministic: tools ordered by slug within each tool_type group
    so the rendered text doesn't churn across calls that didn't change
    the loaded-on-boot set.
    """
    loaded = (
        session.query(Tool)
        .filter(Tool.lifecycle_state == "loaded-on-boot")
        .order_by(Tool.tool_type, Tool.slug)
        .all()
    )
    if not loaded:
        return "No tools currently loaded on boot."

    lines = [f"Loaded-on-boot tools ({len(loaded)} total):"]
    by_type: dict[str, list[str]] = {}
    for t in loaded:
        by_type.setdefault(t.tool_type or "unknown", []).append(t.slug)
    for tool_type in sorted(by_type):
        slugs = ", ".join(by_type[tool_type])
        lines.append(f"- {tool_type}: {slugs}")
    return "\n".join(lines)


def refresh_identity_on_loaded_on_boot_change(
    tool: Tool,
    old_state: str,
    new_state: str,
    *,
    session: Session,
    memory: MemoryClient,
) -> None:
    """Post-transition hook — refreshes the identity note iff the
    transition crosses the `loaded-on-boot` boundary.

    Per Fork 5, the triggering transitions are:
      - ANY state → loaded-on-boot  (gaining a permanent tool)
      - loaded-on-boot → ANY state  (losing a permanent tool,
        including the loaded-on-boot → retired direction which is
        explicitly in-scope)

    All other transitions are no-ops for identity. The "what's in my
    toolbelt" semantic is captured entirely by the loaded-on-boot
    set; non-boundary transitions (e.g. discovered → used) don't
    change it.

    Identity write failures are logged WARN and swallowed — transition
    validation already succeeded at the service layer, so the DB is
    in the new state even if memory is down. Operator sees the stale
    identity until memory recovers; that's acceptable degradation.
    """
    crossed_boundary = (
        old_state == "loaded-on-boot" or new_state == "loaded-on-boot"
    )
    if not crossed_boundary:
        return
    direction = (
        "gained" if new_state == "loaded-on-boot" else "lost"
    )
    log.info(
        "identity.refresh slug=%s direction=%s %s -> %s",
        tool.slug, direction, old_state, new_state,
    )
    try:
        summary = compose_identity_summary(session)
        memory.identity_set(summary)
    except Exception as exc:
        log.warning(
            "identity.refresh_failed slug=%s error=%s: %s",
            tool.slug, type(exc).__name__, exc,
        )
