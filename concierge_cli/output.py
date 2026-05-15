"""Text-mode rendering for CLI responses.

`--json` mode bypasses this module entirely — raw response goes to
stdout via `model_dump_json`. The memory-unavailable banner is
rendered as three content lines bracketed by 80-character rules
because the operator must notice when a recommendation was
generated without memory context; a quiet line is too easy to miss.
"""
from __future__ import annotations

from typing import TextIO

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
