"""MCP resources protocol — expose Concierge's six prompt resources.

This module implements Fix Day 4 Task 2 (narration-as-push pattern 2
per DECISIONS `[2026-04-23]` — Push channel reframed as narration-as-
push). Six resources are advertised under the
`concierge://prompts/{name}.md` URI convention established in
`adapters/claude_code/meta_tools/gap_preamble.py:55-56`:

- `concierge://prompts/tool-awareness.md`           (X3)
- `concierge://prompts/tool-recommendation.md`      (X4)
- `concierge://prompts/tool-discovery.md`           (X6)
- `concierge://prompts/tool-lifecycle-weekly-review.md` (X7-A)
- `concierge://prompts/behavioral-rules.md`         (X8)
- `concierge://prompts/gap-preamble.md`             (adapter-authored)

## Design

The five Class-1 fragments (X3 / X4 / X6 / X7-A / X8) are exposed
**byte-for-byte verbatim** from the Python constants in
`core.prompts`. The Class-1 verbatim invariant (DECISIONS
`[2026-04-21 05:50]`) governs those five: the source constant is
already the canonical content. Any drift check against the original
skill-file source lives in the per-fragment module's docstring and
`SKILL_FRAGMENT_SYNC_LOG.md`, not here.

The gap-preamble is adapter-authored (not Class-1) and exposed
byte-for-byte from `CLAUDE_CODE_GAP_PREAMBLE`. Its X8-anchor-phrase
drift check lives in `tests/test_meta_tools_gap_preamble.py`.

The resource ordering in `CONCIERGE_RESOURCES` (tool-awareness →
tool-recommendation → tool-discovery → tool-lifecycle-weekly-review
→ behavioral-rules → gap-preamble) is the order a session-long
posture reader would want: the three reasoning protocols first
(task decomposition, ranking, discovery), the lifecycle review
protocol fourth, the behavioral rules fifth, the adapter-framed
condensed preamble last as the single-agent-context summary.

## URI scheme

`concierge://prompts/{name}.md` where `{name}` is the kebab-case
source-file name (without the `.md` extension on the Python constant
side). The scheme was documented in `gap_preamble.py:55-56` before
this module existed — Fix Day 4 Task 2 closes that documented
deferral rather than introducing a new surface. See DECISIONS
`[2026-04-25 Fix Day 4]` (forthcoming) for the full path from the
originally-proposed `concierge://preamble/{name}` default to this
audit-discovered `concierge://prompts/{name}.md` precedent.

## Capability advertisement

`register_resources(dispatcher)` declares `resources: {}` on the
dispatcher's capability map, so the `initialize` response tells the
client the server supports the resources protocol. The empty `{}`
indicates we support the base protocol without sub-features
(`subscribe`, `listChanged`) — our resources are static.

## Error semantics

- `resources/list` with any params shape returns the full inventory;
  the method has no parameters per MCP spec.
- `resources/read` missing or non-string `uri` → INVALID_PARAMS.
- `resources/read` with a URI not in the registry → INVALID_PARAMS
  (the URI is an invalid param relative to our registered set; we
  do not expose a resource-not-found as a distinct JSON-RPC error
  code because MCP's standard set does not include one).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from adapters.claude_code.dispatcher import (
    Dispatcher,
    Handler,
    ResourceSpec,
    _ParamsError,
)
from adapters.claude_code.meta_tools.gap_preamble import CLAUDE_CODE_GAP_PREAMBLE
from core.prompts import (
    TOOL_AWARENESS_BEHAVIORAL_RULES__FROM_SOUL_DELTA_MD,
    TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD,
    TOOL_DISCOVERY_PROTOCOL__FROM_TOOL_DISCOVERY_SKILL,
    TOOL_LIFECYCLE_WEEKLY_REVIEW_PROTOCOL__FROM_TOOL_LIFECYCLE_SKILL,
    TOOL_RECOMMENDATION_PROTOCOL__FROM_TOOL_RECOMMENDATION_MD,
)


logger = logging.getLogger(__name__)


CONCIERGE_RESOURCES: list[ResourceSpec] = [
    ResourceSpec(
        uri="concierge://prompts/tool-awareness.md",
        name="Tool Awareness Protocol (X3)",
        description=(
            "Protocol for task decomposition and capability assessment "
            "before acting. Frames when to consult the catalog, when to "
            "search memory, and when a capability gap warrants escalation."
        ),
        mime_type="text/markdown",
        text=TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD,
    ),
    ResourceSpec(
        uri="concierge://prompts/tool-recommendation.md",
        name="Tool Recommendation Protocol (X4)",
        description=(
            "Protocol for ranking tool candidates by task fit, preferring "
            "lightweight options over heavyweight when both would serve "
            "and factoring in already-loaded tools."
        ),
        mime_type="text/markdown",
        text=TOOL_RECOMMENDATION_PROTOCOL__FROM_TOOL_RECOMMENDATION_MD,
    ),
    ResourceSpec(
        uri="concierge://prompts/tool-discovery.md",
        name="Tool Discovery Protocol (X6)",
        description=(
            "Protocol for discovering tools outside the current catalog "
            "via signal-table reasoning and lightweight-first heuristics."
        ),
        mime_type="text/markdown",
        text=TOOL_DISCOVERY_PROTOCOL__FROM_TOOL_DISCOVERY_SKILL,
    ),
    ResourceSpec(
        uri="concierge://prompts/tool-lifecycle-weekly-review.md",
        name="Tool Lifecycle Weekly-Review Protocol (X7-A)",
        description=(
            "Weekly-review protocol for promoting proven tools and "
            "demoting unused ones; criteria for permanent toolbelt "
            "membership vs. session-scope use vs. retirement."
        ),
        mime_type="text/markdown",
        text=TOOL_LIFECYCLE_WEEKLY_REVIEW_PROTOCOL__FROM_TOOL_LIFECYCLE_SKILL,
    ),
    ResourceSpec(
        uri="concierge://prompts/behavioral-rules.md",
        name="Tool-Awareness Behavioral Rules (X8)",
        description=(
            "Behavioral posture rules: capability honesty, planning "
            "discipline, feedback/learning, requesting capabilities, "
            "workaround transparency. Session-long conduct posture."
        ),
        mime_type="text/markdown",
        text=TOOL_AWARENESS_BEHAVIORAL_RULES__FROM_SOUL_DELTA_MD,
    ),
    ResourceSpec(
        uri="concierge://prompts/gap-preamble.md",
        name="Claude Code Adapter Preamble (gap-preamble)",
        description=(
            "Claude Code adapter's condensed behavioral framing — the "
            "single-agent-context mirror of the SOUL-delta rules, "
            "oriented around the concierge meta-tool surface."
        ),
        mime_type="text/markdown",
        text=CLAUDE_CODE_GAP_PREAMBLE,
    ),
]


def register_resources(
    dispatcher: Dispatcher,
    *,
    resources: Optional[list[ResourceSpec]] = None,
) -> None:
    """Declare the `resources` capability and register the six
    Concierge prompt resources plus the two method handlers.

    Call from the shim's `_run_with_cleanup` alongside
    `register_meta_tools(dispatcher)`. Registration is idempotent
    by URI (re-registering the same URI replaces the prior spec)
    and by method name (re-registering a method handler replaces
    the prior handler); tests may inject a custom `resources` list.

    Ordering note: capability declaration must happen BEFORE the
    client's `initialize` request (the `initialize` handler reads
    `d.capabilities()` at dispatch time). Calling this function
    from `_run_with_cleanup` before the stdin-read loop starts
    satisfies that constraint — same pre-stdin-readiness requirement
    the N11 meta-tools operate under (DECISIONS `[2026-04-22 11:48]`).
    """
    specs = resources if resources is not None else CONCIERGE_RESOURCES
    dispatcher.declare_capability("resources", {})
    for spec in specs:
        dispatcher.register_resource(spec)
    dispatcher.register_method("resources/list", _make_handle_resources_list(dispatcher))
    dispatcher.register_method("resources/read", _make_handle_resources_read(dispatcher))
    logger.info(
        "resources.registered count=%d uris=%s",
        len(specs),
        ",".join(spec.uri for spec in specs),
    )


def _make_handle_resources_list(d: Dispatcher) -> Handler:
    """Build the `resources/list` handler. MCP's `resources/list`
    takes no parameters (pagination is a sub-feature we don't
    advertise); any params shape is accepted and ignored.
    """

    async def _handle(params: Optional[Any]) -> dict[str, Any]:
        resources = d.list_resources()
        logger.debug("shim.resources_list count=%d", len(resources))
        return {"resources": resources}

    return _handle


def _make_handle_resources_read(d: Dispatcher) -> Handler:
    """Build the `resources/read` handler. Expects an object params
    dict with a non-empty string `uri`; unknown URIs surface as
    INVALID_PARAMS so the client sees a precise failure locus
    rather than a generic INTERNAL_ERROR.
    """

    async def _handle(params: Optional[Any]) -> dict[str, Any]:
        if not isinstance(params, dict):
            raise _ParamsError(
                f"resources/read expects an object params; got {type(params).__name__}"
            )
        uri = params.get("uri")
        if not isinstance(uri, str) or not uri:
            raise _ParamsError("resources/read requires a non-empty string `uri`")
        spec = d.resolve_resource(uri)
        if spec is None:
            raise _ParamsError(
                f"resource {uri!r} is not registered in this Concierge shim"
            )
        logger.debug("shim.resources_read uri=%s bytes=%d", uri, len(spec.text))
        return {"contents": [spec.to_contents()]}

    return _handle


__all__ = ["CONCIERGE_RESOURCES", "register_resources"]
