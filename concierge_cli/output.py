"""Text-mode rendering for CLI responses.

`--json` mode bypasses this module entirely — raw response goes to
stdout via `model_dump_json`. The memory-unavailable banner is
rendered as three content lines bracketed by 80-character rules
because the operator must notice when a recommendation was
generated without memory context; a quiet line is too easy to miss.
"""
from __future__ import annotations

from typing import TextIO

from core.api.schemas import ToolList, ToolOut
from core.lifecycle_store.schema import RequestDetail
from core.recommend.schemas import RecommendResponse, ToolRecommendation


_RULE = "=" * 80


def render_recommend(response: RecommendResponse, out: TextIO) -> None:
    if not response.memory_available:
        _render_memory_warning(out)

    _render_summary_header(response, out)

    if response.reasoning:
        out.write(f"\n{response.reasoning}\n")

    out.write("\n")
    for rec in response.recommendations:
        _render_one(rec, out)
        out.write("\n")

    if response.side_observations:
        _render_observations(response.side_observations, out)

    _render_footer(response, out)


def _render_memory_warning(out: TextIO) -> None:
    out.write(f"{_RULE}\n")
    out.write("WARNING: MEMORY UNAVAILABLE\n")
    out.write("This recommendation was generated WITHOUT access to memory context.\n")
    out.write("Quality is materially weaker than normal. Treat as a starting point.\n")
    out.write(f"{_RULE}\n\n")


def _render_summary_header(r: RecommendResponse, out: TextIO) -> None:
    n = len(r.recommendations)
    plural = "" if n == 1 else "s"
    secs = r.latency_ms.total / 1000.0
    out.write(
        f"{n} recommendation{plural} "
        f"(model={r.model}, effort={r.effort}, "
        f"memory={r.memory_hit_count} hits, {secs:.1f}s)\n"
    )


def _render_one(rec: ToolRecommendation, out: TextIO) -> None:
    catalog = "in catalog" if rec.is_in_catalog else "discovery"
    badges = [rec.confidence, catalog]
    if rec.category:
        badges.append(rec.category)
    out.write(f"{rec.rank}. {rec.tool_name} [{' | '.join(badges)}]\n")
    out.write(f"   {rec.rationale}\n")
    extras = []
    if rec.install_method:
        extras.append(f"install: {rec.install_method}")
    if rec.risk_cost:
        extras.append(f"risk: {rec.risk_cost}")
    if extras:
        out.write(f"   {' | '.join(extras)}\n")


def _render_observations(observations: list[str], out: TextIO) -> None:
    out.write("Observations:\n")
    for obs in observations:
        out.write(f"- {obs}\n")
    out.write("\n")


def _render_footer(r: RecommendResponse, out: TextIO) -> None:
    tokens = r.token_usage
    lat = r.latency_ms
    parts = []
    if r.stop_reason:
        parts.append(f"stop_reason: {r.stop_reason}")
    parts.append(f"tokens: {tokens.input} in / {tokens.output} out")
    parts.append(
        f"total: {lat.total / 1000:.1f}s "
        f"(mem {lat.memory / 1000:.1f}, "
        f"model {lat.model / 1000:.1f}, "
        f"parse {lat.parse / 1000:.1f})"
    )
    out.write("  ".join(parts) + "\n")


def render_request_tool(response: RequestDetail, out: TextIO) -> None:
    """Render a successful POST /requests confirmation.

    Stage 1A item 5 surface. Short and informational — confirms the
    durable record landed and tells the operator where to look for
    it. Worker-form responses additionally surface the escalation
    target so the filing agent (or operator running the CLI manually)
    sees the routing was recorded.

    Category-agnostic framing per items-5+6 scope clarification — no
    "MCP server" phrasing; the word "request" is sufficient.
    """
    out.write(f"Filed: {response.tool_name}\n")
    out.write(f"  filename: {response.filename}\n")
    out.write(f"  status:   {response.status}\n")
    out.write(f"  folder:   {response.folder}\n")
    if response.escalation_target:
        out.write(f"  routes to: {response.escalation_target}\n")
    if response.category:
        out.write(f"  category: {response.category}\n")


def render_list_active(
    response: ToolList, out: TextIO, *, dormant: bool = False
) -> None:
    """Render a `concierge list-active` catalog inventory.

    Stage 1A item 1b surface. Tools are grouped by pack (unpacked
    tools collected under a trailing `[unpacked]` group), mirroring
    the `concierge_list_active` meta-tool's group-by-pack shape. The
    Stage 1A items-4+7 catalog metadata (`best_for`, `limitation`,
    `agent_owner`, `transport`) renders as indented detail lines so
    the use-case / anti-pattern prose is visible inline.

    `dormant` only changes the header noun — the filter itself was
    already applied server-side by the `/tools` query.
    """
    noun = "dormant" if dormant else "active"
    items = response.items

    if not items:
        out.write(f"No {noun} tools match the current filters.\n")
        return

    by_pack: dict[tuple[str, str], list[ToolOut]] = {}
    unpacked: list[ToolOut] = []
    for tool in items:
        if tool.pack_slug:
            key = (tool.pack_name or tool.pack_slug, tool.pack_slug)
            by_pack.setdefault(key, []).append(tool)
        else:
            unpacked.append(tool)

    pack_count = len(by_pack) + (1 if unpacked else 0)
    out.write(
        f"{response.total} {noun} tool(s) across {pack_count} pack(s).\n\n"
    )

    for pack_name, pack_slug in sorted(by_pack):
        out.write(f"[{pack_name}] ({pack_slug})\n")
        for tool in by_pack[(pack_name, pack_slug)]:
            _render_tool_line(tool, out)
        out.write("\n")

    if unpacked:
        out.write("[unpacked]\n")
        for tool in unpacked:
            _render_tool_line(tool, out)
        out.write("\n")


def _render_tool_line(tool: ToolOut, out: TextIO) -> None:
    badges = [tool.lifecycle_state]
    if tool.category:
        badges.append(tool.category)
    if tool.transport:
        badges.append(tool.transport)
    out.write(f"  {tool.slug} [{' | '.join(badges)}]\n")
    if tool.agent_owner:
        out.write(f"    owner:      {tool.agent_owner}\n")
    if tool.best_for:
        out.write(f"    best for:   {tool.best_for}\n")
    if tool.limitation:
        out.write(f"    limitation: {tool.limitation}\n")
    if tool.succeeded_by:
        out.write(f"    succeeded by: {tool.succeeded_by}\n")


# Past-tense confirmation verb keyed by the action passed from the
# enable / disable subcommands.
_AGENT_CONFIG_VERB = {"enable": "Enabled", "disable": "Disabled"}


def render_agent_config(
    action: str, agent_id: str, server_name: str, out: TextIO
) -> None:
    """Render a `concierge enable` / `concierge disable` confirmation.

    Stage 1A item 1b surface. Short and informational — confirms which
    `mcp.servers` entry changed in which agent's openclaw.json. The
    `.bak` sibling the writer leaves behind is not echoed here; the
    writer logs it, and the path is deterministic from the agent.
    """
    verb = _AGENT_CONFIG_VERB.get(action, f"{action}d")
    out.write(f"{verb}: {server_name}\n")
    out.write(f"  agent:  {agent_id}\n")
    out.write(f"  server: {server_name}\n")
