"""Gap-report generator for the concierge_recommend result payload.

Deterministic post-processor — no second Anthropic call. Walks the
`POST /recommend` response and synthesizes a markdown `### Gap report`
section pinned between `### Top-ranked` and `### Summary` in the
rendered meta-tool result.

## Firing rules

| Sub-section | Fires when |
|---|---|
| `#### Not in catalog (N tool(s))` | ≥1 recommendation has `is_in_catalog=False`. |
| `#### Low-confidence matches` | ≥1 recommendation has `confidence=low`. |
| `#### Memory coverage` | Always fires when the section is non-minimal. Two variants: no-prior-memory vs memory-informed. Memory-unavailable folds into the no-prior-memory variant (the unavailable state is already surfaced in the `### Top-ranked` context line). |
| `#### Suggested next action` | Always fires when the section is non-minimal. Three variants: discovery-route, proceed-with-top, review-carefully. |

## Minimal block

When none of the gap conditions fire — no discoveries, no
low-confidence matches, memory available, memory_hit_count > 0 —
the section collapses to a one-liner:

    No gaps detected — recommendations are in-catalog, no low-confidence
    matches flagged, and prior memory informed the ranking.

Pinned-always presence (per N12 proposal Q1 answer) serves the
soak-diagnostic signal: "No gaps detected" unambiguously means
Concierge evaluated and found none, whereas conditional absence
would create ambiguity at Day-4 log reading between "logic crashed"
and "decided correctly."

## Behavioral voice

The wording of this module's output (especially the Suggested-next-
action phrasing) is informed by `CLAUDE_CODE_GAP_PREAMBLE` in
`gap_preamble.py` — single-agent-framed, Concierge-meta-tool-anchored,
do-not-block-on-approval. See `gap_preamble.py`'s module docstring
for why the preamble is adapter-authored rather than a Class-1
prompt-fragment extract.

## Cut-priority ladder (if 90-min budget exceeded during build)

Pre-specified in the N12 proposal confirmation exchange:

1. First cut: drop `#### Low-confidence matches` entirely (edge-case
   heaviest, least load-bearing for N14 smoke).
2. Second cut: collapse `#### Memory coverage` two-variant logic to
   single-variant "Concierge evaluated prior context" language.
3. Never cut: `#### Not in catalog` and `#### Suggested next action`
   — those are what N14 integration smoke exercises.

No cuts fired at build time; full four-subsection logic shipped.
"""
from __future__ import annotations

from typing import Any


_MINIMAL_BLOCK = (
    "No gaps detected — recommendations are in-catalog, no "
    "low-confidence matches flagged, and prior memory informed "
    "the ranking.\n"
)


def build_gap_report(response: dict[str, Any]) -> str:
    """Return the markdown body of the `### Gap report` section for a
    `concierge_recommend` response. Always returns a non-empty string.

    The caller is responsible for prepending the `### Gap report\\n\\n`
    heading — this function returns only the section body so the
    renderer owns heading-level consistency across the pinned
    markdown structure.
    """
    recommendations = response.get("recommendations", []) or []
    memory_hit_count = response.get("memory_hit_count", 0) or 0
    memory_available = bool(response.get("memory_available", False))

    discoveries = [
        r for r in recommendations if not r.get("is_in_catalog", False)
    ]
    low_confidence = [
        r for r in recommendations if r.get("confidence") == "low"
    ]

    has_gap_signal = (
        bool(discoveries)
        or bool(low_confidence)
        or not memory_available
        or memory_hit_count == 0
        or not recommendations
    )

    if not has_gap_signal:
        return _MINIMAL_BLOCK

    sections: list[str] = []

    if discoveries:
        sections.append(_render_not_in_catalog(discoveries))

    if low_confidence:
        sections.append(_render_low_confidence(low_confidence))

    # Memory coverage fires only when there are recommendations to
    # assess. An empty recommendations list goes straight to the SNA
    # catch-all ("rephrase or browse"); emitting memory-coverage
    # phrasing there would be misleading (no ranking to inform).
    if recommendations:
        sections.append(
            _render_memory_coverage(
                memory_hit_count=memory_hit_count,
                memory_available=memory_available,
            )
        )

    sections.append(
        _render_suggested_next_action(
            recommendations=recommendations,
            discoveries=discoveries,
            low_confidence=low_confidence,
            memory_hit_count=memory_hit_count,
            memory_available=memory_available,
        )
    )

    return "\n\n".join(sections) + "\n"


# ---- Sub-section renderers ----------------------------------------------


def _render_not_in_catalog(discoveries: list[dict[str, Any]]) -> str:
    count = len(discoveries)
    noun = "tool" if count == 1 else "tools"
    lines = [f"#### Not in catalog ({count} {noun})", ""]
    for d in discoveries:
        name = d.get("tool_name", "(unnamed)")
        lines.append(
            f"- **{name}** — discovery. To add to the Concierge catalog, "
            "call `concierge_request_tool` with the evidence you gathered."
        )
    return "\n".join(lines)


def _render_low_confidence(low_confidence: list[dict[str, Any]]) -> str:
    lines = ["#### Low-confidence matches", ""]
    for r in low_confidence:
        name = r.get("tool_name", "(unnamed)")
        lines.append(
            f"- **{name}** — Concierge's confidence on this match is low. "
            "Verify the rationale before committing to this tool."
        )
    return "\n".join(lines)


def _render_memory_coverage(
    *, memory_hit_count: int, memory_available: bool
) -> str:
    if memory_hit_count > 0 and memory_available:
        noun = "tool-decision" if memory_hit_count == 1 else "tool-decisions"
        body = (
            f"Concierge found {memory_hit_count} prior {noun} for similar "
            "tasks; prior context informed the ranking."
        )
    else:
        # Folds memory_unavailable into the no-prior-memory variant.
        # The memory_available=False signal is already surfaced in the
        # ### Top-ranked context line, so repeating it here would add
        # noise without signal.
        body = (
            "Concierge has no prior tool-decision memory for this task "
            "pattern. This is a novel request; your choice here will "
            "shape future recommendations."
        )
    return f"#### Memory coverage\n\n{body}"


def _render_suggested_next_action(
    *,
    recommendations: list[dict[str, Any]],
    discoveries: list[dict[str, Any]],
    low_confidence: list[dict[str, Any]],
    memory_hit_count: int,
    memory_available: bool,
) -> str:
    body = _choose_suggested_next_action_body(
        recommendations=recommendations,
        discoveries=discoveries,
        low_confidence=low_confidence,
        memory_hit_count=memory_hit_count,
        memory_available=memory_available,
    )
    return f"#### Suggested next action\n\n{body}"


def _choose_suggested_next_action_body(
    *,
    recommendations: list[dict[str, Any]],
    discoveries: list[dict[str, Any]],
    low_confidence: list[dict[str, Any]],
    memory_hit_count: int,
    memory_available: bool,
) -> str:
    # Variant 1 — discovery-route. The preamble's "do not block on
    # approval" guidance is baked into the phrasing here.
    if discoveries:
        top_discovery = discoveries[0]
        if top_discovery.get("confidence") in ("high", "medium"):
            name = top_discovery.get("tool_name", "(unnamed)")
            return (
                f"File a `concierge_request_tool` call for **{name}** if "
                "you have validated the evidence. Do not block your "
                "current task — continue with existing tools while the "
                "request is reviewed."
            )

    # Variant 2 — proceed-with-top. Requires a clean happy path: no
    # discoveries, no low-confidence, memory healthy, all recs
    # high-confidence, and at least one rec to point at.
    all_high = (
        bool(recommendations)
        and all(r.get("confidence") == "high" for r in recommendations)
    )
    if (
        all_high
        and not low_confidence
        and not discoveries
        and memory_available
        and memory_hit_count > 0
    ):
        top = recommendations[0]
        name = top.get("tool_name", "(unnamed)")
        return (
            f"Proceed with **{name}** unless you see a reason not to — "
            "recommendations are high-confidence and backed by prior "
            "memory."
        )

    # Variant 3 — review-carefully. Catch-all for ambiguous cases
    # (medium confidence, missing memory, mixed signals with no
    # actionable discovery).
    if recommendations:
        top = recommendations[0]
        name = top.get("tool_name", "(unnamed)")
        confidence = top.get("confidence", "unknown")
        return (
            f"Review the recommendations carefully. Top match is "
            f"**{name}** at **{confidence}** confidence; consider "
            "alternatives if the rationale does not resonate."
        )

    return (
        "No recommendations were returned. Consider rephrasing the task "
        "or using `concierge_list_active` to browse the catalog directly."
    )
