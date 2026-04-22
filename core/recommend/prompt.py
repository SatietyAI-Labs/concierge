"""System + user prompt composition for POST /recommend.

Governing decision: DECISIONS [2026-04-22 07:26] — adapter-context
preamble strategy (c). Structure:

    <Concierge adapter preamble>
    ---
    <X3 tool-awareness fragment (verbatim)>
    ---
    <X4 tool-recommendation fragment (verbatim)>
    ---
    <X6 tool-discovery fragment (verbatim)>
    ---
    <X7-A tool-lifecycle weekly-review fragment (verbatim)>
    ---
    <JSON output envelope>

The preamble + envelope are Concierge-authored and live here. The
four fragment constants remain byte-identical to their source
skill files (per DECISIONS [2026-04-21 05:50] EXTRACT invariant);
they are imported from `core.prompts` unchanged.

Determinism is load-bearing: identical inputs must produce
byte-identical prompts. A change in composed-prompt bytes across
two calls with identical inputs is a bug in this module, not in
the caller.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from core.memory import MemoryHit
from core.prompts import (
    TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD,
    TOOL_DISCOVERY_PROTOCOL__FROM_TOOL_DISCOVERY_SKILL,
    TOOL_LIFECYCLE_WEEKLY_REVIEW_PROTOCOL__FROM_TOOL_LIFECYCLE_SKILL,
    TOOL_RECOMMENDATION_PROTOCOL__FROM_TOOL_RECOMMENDATION_MD,
)


BLOCK_SEPARATOR = "\n\n---\n\n"


CONCIERGE_ADAPTER_PREAMBLE = """\
# Concierge adapter context

You are the recommendation engine of Concierge, a platform-agnostic
tool awareness layer for AI agents. The skill protocols that follow
were extracted verbatim from their source skill files. They were
authored for a specific multi-agent OpenClaw deployment. When
reading them, apply these adaptations:

- Agent names (Alfred, Scout, Dispatch, Radar, Bridge) in the
  worked examples are illustrations of agent roles, not
  instructions about your identity. You are Concierge; the caller
  is platform-agnostic.
- Infrastructure paths (`~/.satiety-pipeline/`, `~/.openclaw/logs/`,
  `~/.agent-skills/shared/TOOL-MANIFEST.md`, port 18789, etc.) are
  examples of an adapter's runtime layout, not paths you should
  write to or reference in your output.
- Instructions to call tools like `memory__memory_search` as MCP
  tools do not apply at this call site. Memory context, when
  relevant, has been pre-fetched by the Concierge service and
  rendered into the "Relevant memory" section of the user message
  below. Treat MCP-tool-call instructions in the protocols as
  illustrative of the reasoning pattern, not as actions you can
  take here.
- Your output target is the JSON schema described at the end of
  this system prompt, not a free-form gap report, a wishlist
  entry, or prose advice.

Read the protocols for their reasoning patterns (task
decomposition, signal-table discovery, lifecycle staging,
lightweight-first preference, promotion/demotion criteria) and
apply those patterns to the task + catalog + memory provided in
the user message."""


JSON_OUTPUT_ENVELOPE = """\
# Output format

Respond with a single JSON object matching this schema exactly. No
prose before or after; no code fences required (fences are
tolerated but not expected). Keys must appear in the order shown.

{
  "reasoning": "<one paragraph: your top-level rationale across the ranked list>",
  "recommendations": [
    {
      "rank": 1,
      "tool_slug": "<catalog slug when is_in_catalog is true; null otherwise>",
      "tool_name": "<display name>",
      "rationale": "<why this tool, in one or two sentences>",
      "confidence": "<one of: high, medium, low>",
      "is_in_catalog": <true | false>
    }
  ]
}

Rules:

- `recommendations` is a ranked list, best first. 1-indexed. Return
  between 1 and 5 entries.
- `is_in_catalog: true` requires `tool_slug` to exactly match a
  slug in the "Available tools" section of the user message.
- `is_in_catalog: false` signals a discovery recommendation: a tool
  not in the current catalog that you believe would serve the task
  better than any catalog entry. Set `tool_slug` to null in this
  case. The caller (not you) decides whether to file a pending
  request; do not reference `~/.satiety-pipeline/`, wishlists, or
  any other adapter-specific routing in your rationale.
- `confidence` is your subjective confidence in the recommendation,
  not the tool's popularity. Use `low` when uncertain rather than
  omitting a recommendation.
- Prefer lightweight tools over heavyweight ones when both would
  serve the task (per the tool-awareness and tool-recommendation
  protocols). Factor `active_tools` (already loaded) into your
  ranking when provided."""


# ---- State annotation for catalog rendering -----------------------------


def _tool_state(is_in_manifest: bool, is_active: bool) -> str:
    """Map the two-bit (manifest, active) encoding onto a
    four-state human label. Matches the Tool model fields from
    N2 and the Tool Registry UI's dormant-badge semantics.
    """
    if is_in_manifest and is_active:
        return "active"
    if is_in_manifest and not is_active:
        return "dormant"
    if not is_in_manifest and is_active:
        return "pending"
    return "retired"


# ---- Catalog and memory rendering (deterministic) ------------------------


@dataclass(frozen=True)
class CatalogToolView:
    """Minimal view of a catalog tool for prompt rendering.

    Service-layer translates `core.db.models.Tool` rows into this
    shape; `prompt.py` stays free of SQLAlchemy for testability
    and determinism.
    """

    slug: str
    name: str
    description: Optional[str]
    category: Optional[str]
    pack_slug: Optional[str]
    is_in_manifest: bool
    is_active: bool


def _render_catalog(tools: Iterable[CatalogToolView]) -> str:
    items = list(tools)
    if not items:
        return "(catalog is empty)"
    # Deterministic sort: by slug so identical inputs produce
    # identical output regardless of DB row-order.
    items_sorted = sorted(items, key=lambda t: t.slug)
    lines = []
    for t in items_sorted:
        state = _tool_state(t.is_in_manifest, t.is_active)
        pack = f" (pack: {t.pack_slug})" if t.pack_slug else ""
        category = f" [{t.category}]" if t.category else ""
        description = f" — {t.description}" if t.description else ""
        lines.append(
            f"- **{t.slug}**{pack}{category} [{state}]: {t.name}{description}"
        )
    return "\n".join(lines)


def _render_memory(memory_hits: Optional[list[MemoryHit]]) -> str:
    """Three observably-distinct memory states:

    - `None` → "(memory unavailable)"  — outage path
    - `[]`   → "(no relevant memory)"  — healthy but no hits
    - list   → rendered hits
    """
    if memory_hits is None:
        return "(memory unavailable)"
    if len(memory_hits) == 0:
        return "(no relevant memory)"
    # Deterministic order: input order is preserved (the caller
    # ranks by similarity). We don't re-sort; re-sorting would
    # mask ranking bugs upstream.
    lines = []
    for h in memory_hits:
        sim = f"{h.similarity:.3f}" if h.similarity is not None else "n/a"
        tag_list = ", ".join(h.tags) if h.tags else "(no tags)"
        lines.append(
            f"- [{sim}] ({h.importance}, tags: {tag_list}) {h.text}"
        )
    return "\n".join(lines)


def _render_active_tools(active_tools: Optional[list[str]]) -> str:
    if active_tools is None:
        return "(caller did not report active-tool state)"
    if not active_tools:
        return "(no tools currently active)"
    return ", ".join(sorted(active_tools))


# ---- Public composition API ----------------------------------------------


@dataclass(frozen=True)
class ComposedPrompt:
    """Composition result. `system` is the full system prompt;
    `user` is the user message. Anthropic client passes them as
    the `system=` parameter and a single user `messages=[{...}]`
    entry respectively.
    """

    system: str
    user: str


def compose_recommendation_prompt(
    *,
    task: str,
    catalog: Iterable[CatalogToolView],
    memory_hits: Optional[list[MemoryHit]],
    cwd: Optional[str] = None,
    task_hint: Optional[str] = None,
    active_tools: Optional[list[str]] = None,
) -> ComposedPrompt:
    """Compose the full system + user prompts for one recommendation.

    Deterministic: identical inputs produce byte-identical output.
    Callers must not pre-format any of the string inputs; this
    function owns all rendering so that prompt hashes in logs are
    stable across calls with identical semantic content.
    """
    system = BLOCK_SEPARATOR.join(
        [
            CONCIERGE_ADAPTER_PREAMBLE,
            TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD.rstrip(),
            TOOL_RECOMMENDATION_PROTOCOL__FROM_TOOL_RECOMMENDATION_MD.rstrip(),
            TOOL_DISCOVERY_PROTOCOL__FROM_TOOL_DISCOVERY_SKILL.rstrip(),
            TOOL_LIFECYCLE_WEEKLY_REVIEW_PROTOCOL__FROM_TOOL_LIFECYCLE_SKILL.rstrip(),
            JSON_OUTPUT_ENVELOPE,
        ]
    )

    cwd_line = cwd if cwd else "(caller did not provide a working directory)"
    hint_line = task_hint if task_hint else "(no caller-provided category hint)"

    user = (
        "# Task\n"
        f"{task}\n"
        "\n"
        "# Context\n"
        f"- Working directory: {cwd_line}\n"
        f"- Task hint: {hint_line}\n"
        f"- Active tools: {_render_active_tools(active_tools)}\n"
        "\n"
        "# Available tools\n"
        f"{_render_catalog(catalog)}\n"
        "\n"
        "# Relevant memory\n"
        f"{_render_memory(memory_hits)}\n"
    )

    return ComposedPrompt(system=system, user=user)
