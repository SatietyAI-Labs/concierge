"""System + user prompt composition for POST /recommend.

Governing decision: DECISIONS [2026-04-22 07:26] — adapter-context
preamble strategy (c). Structure:

    <Concierge adapter preamble>
    ---
    <X3 tool-awareness fragment>
    ---
    <X4 tool-recommendation fragment>
    ---
    <X6 tool-discovery fragment>
    ---
    <X7-A tool-lifecycle weekly-review fragment>
    ---
    <JSON output envelope>

The preamble + envelope are Concierge-authored and live here. The
four fragment constants are imported from `core.prompts`. They are
Concierge-canonical (formerly byte-identical to OpenClaw skill
sources per DECISIONS [2026-04-21 05:50] EXTRACT invariant; that
invariant was retired per DECISIONS [2026-04-29 Day 8] when
Concierge transitioned to a standalone public artifact).

Determinism is load-bearing: identical inputs must produce
byte-identical prompts. A change in composed-prompt bytes across
two calls with identical inputs is a bug in this module, not in
the caller.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass


log = logging.getLogger(__name__)
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
originate from an OpenClaw multi-agent fleet context; their worked
examples reference a fleet (Alfred, Scout, Dispatch, Radar, Bridge)
and a shared filesystem layout (`~/.satiety-pipeline/`,
`~/.openclaw/logs/`, etc.) as illustrative backdrop. When reading
them, apply these adaptations:

- Agent names in worked examples are illustrations of agent roles
  in a multi-agent fleet, not instructions about your identity.
  You are Concierge; the caller is platform-agnostic.
- Filesystem paths in worked examples (pipeline directories,
  log files, task queues) are illustrative of a host adapter's
  runtime layout, not paths you should write to or reference
  in your output.
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
      "is_in_catalog": <true | false>,
      "category": "<semantic domain, e.g. 'search', 'data-processing'; null if no confident category>",
      "install_method": "<normalized method, e.g. 'apt', 'pip-user', 'npx-mcp', 'npm-global', 'binary'; null if unknown>",
      "risk_cost": "<one phrase: install weight / runtime cost / license; null if nothing material>"
    }
  ],
  "side_observations": [
    "<short adjacent observation, one per string; omit the key or return [] when no observation applies>"
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
- `category`, `install_method`, and `risk_cost` MUST be present on
  every recommendation. Copy them from the catalog entry when
  `is_in_catalog: true` (catalog rows render `<tool_type>` and
  `install=<method>` annotations you can re-use). For discovery,
  infer them. Use `null` explicitly when you have no confident
  value — omitting the key is drift and surfaces as a warning.
- Prefer lightweight tools over heavyweight ones when both would
  serve the task (per the tool-awareness and tool-recommendation
  protocols). Factor `active_tools` (already loaded) into your
  ranking when provided.

## side_observations (optional, at most two entries)

`side_observations` is an array of at most two short observations
(each under 140 characters). The agent caller surfaces these in its
narration to the operator alongside the recommendations, so they
must be observations the operator would actually want to act on —
not re-statements of the recommendation itself.

Trigger ONLY on either of these two specific patterns. Do not
fabricate observations to fill space; silence is correct when
neither pattern fires.

1. **Retired-tool overlap.** A catalog row annotated `[retired]`
   would plausibly have served this task. Example phrasing:
   "`<slug>` is retired but would fit this task — operator may
   want to reinstate if the retirement was premature." Only surface
   when the retired tool's category or capability genuinely
   overlaps the task; do not mention every retired row.

2. **Idle loaded-on-boot tool.** A catalog row annotated
   `[loaded-on-boot]` whose category or stated capability matches
   the task's domain, but which has no recent usage evidence in
   the rendered memory / catalog. Example phrasing: "`<slug>` is
   loaded-on-boot but hasn't been applied to {domain} tasks
   recently — consider using it here instead of recommending a
   new install." Only surface when the idle tool plausibly fits;
   loaded-on-boot tools outside the current domain should not
   trigger this.

If neither pattern applies, omit the key entirely or return `[]`.
Returning more than two observations is drift — pick the two most
actionable and drop the rest."""


# ---- Catalog and memory rendering (deterministic) ------------------------


@dataclass(frozen=True)
class CatalogToolView:
    """Minimal view of a catalog tool for prompt rendering.

    Service-layer translates `core.db.models.Tool` rows into this
    shape; `prompt.py` stays free of SQLAlchemy for testability
    and determinism.

    `tool_type` and `install_method` are surfaced to Opus so the
    rich in-chat content fields (category / install_method /
    risk_cost on each recommendation) can be copied from the
    catalog entry rather than re-derived by Opus.

    `path` and `ambient_loading` are skills-specific: skills sit in
    the context via ambient triggers rather than per-session loads,
    so Opus needs to reason about "this capability is already
    available as a skill" differently from "install this CLI tool."
    Non-skill rows carry `path=None, ambient_loading=None` and render
    with the prior MCP/CLI/HTTP branch unchanged.
    """

    slug: str
    name: str
    description: Optional[str]
    category: Optional[str]
    pack_slug: Optional[str]
    is_in_manifest: bool
    tool_type: Optional[str] = None
    install_method: Optional[str] = None
    path: Optional[str] = None
    ambient_loading: Optional[bool] = None
    # Canonical state per §D audit (Fix Day 3 Task 3) — the stored
    # `Tool.lifecycle_state`. `Optional` only so a malformed view is
    # still renderable: when None, `_render_standard_row` emits a WARN
    # naming the slug and renders the literal `unknown` state. The
    # `Tool.lifecycle_state` column is NOT-NULL, so this never fires for
    # a DB-sourced view in production — the WARN is cheap detection for
    # a directly-constructed view (a test) or a future regression. The
    # legacy `(is_in_manifest, is_active)` fallback derivation was
    # removed with the `is_active` column retirement (DECISIONS D112).
    lifecycle_state: Optional[str] = None


def _render_catalog(tools: Iterable[CatalogToolView]) -> str:
    items = list(tools)
    if not items:
        return "(catalog is empty)"
    # Deterministic sort: by slug so identical inputs produce
    # identical output regardless of DB row-order.
    items_sorted = sorted(items, key=lambda t: t.slug)
    lines = []
    for t in items_sorted:
        if t.tool_type == "skill":
            lines.append(_render_skill_row(t))
        else:
            lines.append(_render_standard_row(t))
    return "\n".join(lines)


def _render_standard_row(t: CatalogToolView) -> str:
    """MCP / CLI / HTTP rendering. Skills get a different shape below.

    Uses the canonical stored `lifecycle_state`. The `Tool.lifecycle_state`
    column is NOT-NULL, so a DB-sourced view always carries it; a `None`
    here means a directly-constructed view (a test) or a future
    regression — the WARN names the slug and the row renders the literal
    `unknown` state so the anomaly is observable rather than crashing.
    The legacy `(is_in_manifest, is_active)` fallback derivation was
    removed with the `is_active` column retirement (DECISIONS D112).
    """
    if t.lifecycle_state is not None:
        state = t.lifecycle_state
    else:
        log.warning(
            "recommend.prompt.lifecycle_state_missing slug=%s "
            "— rendering state=unknown; this should never fire for a "
            "DB-sourced view (lifecycle_state is NOT-NULL)",
            t.slug,
        )
        state = "unknown"
    pack = f" (pack: {t.pack_slug})" if t.pack_slug else ""
    category = f" [{t.category}]" if t.category else ""
    tool_type = f" <{t.tool_type}>" if t.tool_type else ""
    install = f" install={t.install_method}" if t.install_method else ""
    description = f" — {t.description}" if t.description else ""
    return (
        f"- **{t.slug}**{pack}{tool_type}{category} [{state}]{install}: "
        f"{t.name}{description}"
    )


def _render_skill_row(t: CatalogToolView) -> str:
    """Skills rendering.

    Skills differ from MCP/CLI/HTTP in two ways Opus needs to see:

    - They are **ambient-loaded**: the SKILL.md enters context when
      its trigger conditions match, not via an explicit install or
      load step. Recommending a skill means "invoke this ambient
      capability" — there is no `install_method` to copy into the
      rich in-chat content fields. Opus should set `install_method`
      to `null` for skill recommendations.
    - Their `path` points at a SKILL.md file, so downstream tools
      (and the narration-as-push layer in Fix Day 4) can reference
      it directly rather than re-discovering where the skill lives.
    """
    category = f" [{t.category}]" if t.category else ""
    description = f" — {t.description}" if t.description else ""
    ambient_tag = "ambient" if t.ambient_loading else "on-demand"
    path = f" path={t.path}" if t.path else ""
    return (
        f"- **{t.slug}** <skill>{category} [{ambient_tag}]{path}: "
        f"{t.name}{description}"
    )


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


def _render_agent_id(agent_id: Optional[str]) -> str:
    """Render the caller-agent identifier line (Stage 1A item 3).

    Always returns a string so the `# Context` block renders a fourth
    line unconditionally — matches the sentinel pattern used by
    `cwd` / `task_hint` / `active_tools` above. Strips whitespace
    defensively; a whitespace-only `agent_id` collapses to the
    sentinel rather than rendering as an empty value.
    """
    if not agent_id or not agent_id.strip():
        return "(no caller-provided agent identifier)"
    return agent_id.strip()


def _render_agent_identity_section(agent_identity: Optional[str]) -> str:
    """Render the per-agent identity section for the user prompt, or "".

    The calling agent's migrated identity notes (Stage 1A item 8 —
    `MemoryClient.identity_get_agent`, populated by the identity-notes
    migration) render as a `# Calling agent identity` section between
    the `# Context` block and `# Available tools`, expanding on the
    `- Calling agent:` line with the agent's own role/identity prose.

    Returns `""` when `agent_identity` is None, empty, or
    whitespace-only — the section collapses entirely (header
    included), so the user prompt stays byte-identical to a call
    without per-agent identity. A populated value renders the header,
    the stripped content, and a trailing blank-line separator so the
    section slots cleanly before `# Available tools`.

    Distinct from `_render_identity_block` (the operator tool-prefs
    note): that block lives in the *system* prompt and is identical
    for every caller; this section lives in the *user* prompt and
    varies by `agent_id`, so it must stay out of the agent-agnostic
    system prompt.
    """
    if not agent_identity or not agent_identity.strip():
        return ""
    return f"# Calling agent identity\n\n{agent_identity.strip()}\n\n"


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


def _render_identity_block(identity: Optional[str]) -> Optional[str]:
    """Render the operator-identity block, or return None when absent.

    Per Fix Day 3 Fork 4, the identity block sits between the adapter
    preamble and the X3 tool-awareness fragment — right after
    role-setting, before the behavioral protocols. None when identity
    is unset OR empty: a missing/empty identity collapses the block
    entirely rather than rendering a "no identity available" sentinel
    that would inflate every prompt pointlessly.
    """
    if not identity or not identity.strip():
        return None
    return f"# Operator identity\n\n{identity.strip()}"


def compose_recommendation_prompt(
    *,
    task: str,
    catalog: Iterable[CatalogToolView],
    memory_hits: Optional[list[MemoryHit]],
    cwd: Optional[str] = None,
    task_hint: Optional[str] = None,
    active_tools: Optional[list[str]] = None,
    identity: Optional[str] = None,
    agent_id: Optional[str] = None,
    agent_identity: Optional[str] = None,
) -> ComposedPrompt:
    """Compose the full system + user prompts for one recommendation.

    Deterministic: identical inputs produce byte-identical output.
    Callers must not pre-format any of the string inputs; this
    function owns all rendering so that prompt hashes in logs are
    stable across calls with identical semantic content.

    `identity` (Fix Day 3 Task 7) is an optional operator-identity
    summary pulled from `MemoryClient.identity_get()`. When set and
    non-empty, it inserts between the adapter preamble and the X3
    fragment so Opus has persistent operator context before the
    behavioral protocols. Absent/empty identity is a no-op — the
    block collapses entirely and the surrounding blocks stay
    byte-identical to the pre-identity composition.

    `agent_id` (Stage 1A item 3) is an optional caller-agent
    identifier. When set, it renders as a fourth line in the user
    prompt's `# Context` block (alongside working directory, task
    hint, and active tools) so Opus sees who the caller is. When
    absent or whitespace-only, the line still renders with the
    sentinel `(no caller-provided agent identifier)` — symmetric
    with cwd/task_hint/active_tools.

    `agent_identity` (Stage 1A recommend-prompt wiring slice) is the
    calling agent's migrated identity notes — the text returned by
    `MemoryClient.identity_get_agent(agent_id)`. When set and
    non-empty, it renders as a `# Calling agent identity` section
    between the `# Context` block and `# Available tools`, expanding
    on the `- Calling agent:` line with the agent's own role/identity
    prose. Absent/empty `agent_identity` is a no-op — the section
    collapses entirely and the user prompt stays byte-identical to a
    call without per-agent identity. The service passes this only
    when the request carries an `agent_id`; per-agent identity is a
    user-prompt concern (it varies by caller) and never enters the
    agent-agnostic system prompt.
    """
    system_blocks = [CONCIERGE_ADAPTER_PREAMBLE]
    identity_block = _render_identity_block(identity)
    if identity_block is not None:
        system_blocks.append(identity_block)
    system_blocks.extend(
        [
            TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD.rstrip(),
            TOOL_RECOMMENDATION_PROTOCOL__FROM_TOOL_RECOMMENDATION_MD.rstrip(),
            TOOL_DISCOVERY_PROTOCOL__FROM_TOOL_DISCOVERY_SKILL.rstrip(),
            TOOL_LIFECYCLE_WEEKLY_REVIEW_PROTOCOL__FROM_TOOL_LIFECYCLE_SKILL.rstrip(),
            JSON_OUTPUT_ENVELOPE,
        ]
    )
    system = BLOCK_SEPARATOR.join(system_blocks)

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
        f"- Calling agent: {_render_agent_id(agent_id)}\n"
        "\n"
        f"{_render_agent_identity_section(agent_identity)}"
        "# Available tools\n"
        f"{_render_catalog(catalog)}\n"
        "\n"
        "# Relevant memory\n"
        f"{_render_memory(memory_hits)}\n"
    )

    return ComposedPrompt(system=system, user=user)
