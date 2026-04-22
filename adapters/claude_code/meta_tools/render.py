"""Pinned markdown rendering for meta-tool results.

## Why pinned

Each handler returns an MCP `tools/call` result with a single text
content item. The text's markdown structure is **pinned** (section
headings + ordering) so N12's forthcoming gap-report injection has
a known insertion point rather than having to parse variable output.

## The three contracts

### concierge_recommend

    ## Recommendations

    **Context:** model=<model>, memory_available=<bool>, memory_hits=<n>, request_id=<short>

    ### Top-ranked

    1. **<tool_name>** — <rationale>
       *confidence: <high|medium|low> · catalog: <yes|discovery> · slug: `<slug>`*

    2. **<tool_name>** — ...

    ### Summary

    <reasoning or "(no summary provided)">

**N12 contract:** insert a new `### Gap report` section between the
`### Top-ranked` block and the `### Summary` block. Ordering is the
grammar; heading text is the anchor.

### concierge_request_tool

    ## Tool request filed

    - **Tool:** <tool_name>
    - **Filename:** `<filename>`
    - **Folder:** pending
    - **Request ID:** <id>

    The operator will review. Continue with your current task using
    existing tools.

### concierge_list_active

    ## Active tools

    <total> tool(s) across <n> pack(s).

    ### <pack_name> (`<pack_slug>`)

    - **`<slug>`** — <description>

    ### (unpacked)

    - **`<slug>`** — <description>

## Error rendering

On backing-service failures, handlers return an MCP `isError=True`
result with one text content item describing the class of failure
in operator-actionable terms. The shape is identical (single text
content item) so the MCP client's rendering is consistent whether
the outcome succeeded or failed.
"""
from __future__ import annotations

from typing import Any


# ---- MCP result envelope -------------------------------------------------


def ok_result(markdown: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": markdown}],
        "isError": False,
    }


def error_result(markdown: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": markdown}],
        "isError": True,
    }


# ---- concierge_recommend -------------------------------------------------


def _short_request_id(request_id: str) -> str:
    return request_id[:12] if len(request_id) >= 12 else request_id


def render_recommend_result(response: dict[str, Any]) -> str:
    """Render `POST /recommend` JSON body as pinned markdown.

    Accepts the already-parsed response dict (not the raw httpx
    Response). Handlers are responsible for parsing before calling.
    """
    request_id = response.get("request_id", "")
    model = response.get("model", "")
    memory_available = response.get("memory_available", False)
    memory_hits = response.get("memory_hit_count", 0)
    recommendations = response.get("recommendations", []) or []
    reasoning = response.get("reasoning")

    context_line = (
        f"**Context:** model={model}, "
        f"memory_available={memory_available}, "
        f"memory_hits={memory_hits}, "
        f"request_id={_short_request_id(request_id)}"
    )

    lines = ["## Recommendations", "", context_line, "", "### Top-ranked", ""]

    if not recommendations:
        lines.append("*(no recommendations returned — the task may not have surfaced a clear gap)*")
    else:
        for rec in recommendations:
            rank = rec.get("rank", "?")
            tool_name = rec.get("tool_name", "(unnamed)")
            rationale = rec.get("rationale", "")
            confidence = rec.get("confidence", "?")
            is_in_catalog = rec.get("is_in_catalog", False)
            slug = rec.get("tool_slug")

            catalog_tag = "yes" if is_in_catalog else "discovery"
            slug_tag = f" · slug: `{slug}`" if slug else ""

            lines.append(f"{rank}. **{tool_name}** — {rationale}")
            lines.append(
                f"   *confidence: {confidence} · catalog: {catalog_tag}{slug_tag}*"
            )
            lines.append("")

    lines.append("### Summary")
    lines.append("")
    lines.append(reasoning if reasoning else "*(no summary provided)*")
    lines.append("")

    return "\n".join(lines)


# ---- concierge_request_tool ----------------------------------------------


def render_request_tool_result(response: dict[str, Any]) -> str:
    tool_name = response.get("tool_name") or "(unnamed)"
    filename = response.get("filename") or "(unknown)"
    folder = response.get("folder") or "pending"
    request_id = response.get("id")
    request_id_str = str(request_id) if request_id is not None else "(pending reconcile)"

    lines = [
        "## Tool request filed",
        "",
        f"- **Tool:** {tool_name}",
        f"- **Filename:** `{filename}`",
        f"- **Folder:** {folder}",
        f"- **Request ID:** {request_id_str}",
        "",
        "The operator will review. Continue with your current task using existing tools.",
        "",
    ]
    return "\n".join(lines)


# ---- concierge_list_active -----------------------------------------------


def render_list_active_result(response: dict[str, Any]) -> str:
    items = response.get("items", []) or []
    total = response.get("total", 0)

    by_pack: dict[tuple[str, str], list[dict[str, Any]]] = {}
    unpacked: list[dict[str, Any]] = []
    for item in items:
        pack_slug = item.get("pack_slug")
        pack_name = item.get("pack_name") or pack_slug or ""
        if pack_slug:
            by_pack.setdefault((pack_name, pack_slug), []).append(item)
        else:
            unpacked.append(item)

    pack_count = len(by_pack) + (1 if unpacked else 0)

    lines = [
        "## Active tools",
        "",
        f"{total} tool(s) across {pack_count} pack(s).",
        "",
    ]

    for (pack_name, pack_slug) in sorted(by_pack.keys()):
        lines.append(f"### {pack_name} (`{pack_slug}`)")
        lines.append("")
        for item in by_pack[(pack_name, pack_slug)]:
            slug = item.get("slug", "(unknown)")
            desc = item.get("description") or "*(no description)*"
            lines.append(f"- **`{slug}`** — {desc}")
        lines.append("")

    if unpacked:
        lines.append("### (unpacked)")
        lines.append("")
        for item in unpacked:
            slug = item.get("slug", "(unknown)")
            desc = item.get("description") or "*(no description)*"
            lines.append(f"- **`{slug}`** — {desc}")
        lines.append("")

    if not items:
        lines.append("*(no active tools match the current filters)*")
        lines.append("")

    return "\n".join(lines)


# ---- Error renderers -----------------------------------------------------


def render_service_unavailable(url: str, detail: str) -> str:
    return (
        "## Concierge service unavailable\n"
        "\n"
        f"Could not reach the Concierge HTTP service at `{url}`.\n"
        "\n"
        f"**Detail:** {detail}\n"
        "\n"
        "Check that the service is running and that `CONCIERGE_URL` "
        "points to it. Continue your current task with existing tools.\n"
    )


def render_service_error(status_code: int, body: str) -> str:
    return (
        "## Concierge service returned an error\n"
        "\n"
        f"**HTTP {status_code}.**\n"
        "\n"
        f"Response body (truncated):\n\n```\n{body[:2000]}\n```\n"
        "\n"
        "This indicates a Concierge-service-side problem, not a "
        "client error. Continue your current task with existing "
        "tools; the operator should check the service log.\n"
    )


def render_malformed_response(detail: str) -> str:
    return (
        "## Concierge service returned an unexpected response\n"
        "\n"
        "The service responded successfully but the payload did not "
        "match the expected shape.\n"
        "\n"
        f"**Detail:** {detail}\n"
        "\n"
        "Continue your current task; the operator should investigate.\n"
    )
