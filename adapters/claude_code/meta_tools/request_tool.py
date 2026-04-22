"""concierge_request_tool meta-tool — backs on POST /requests (N7).

Second-priority N11 meta-tool. Files a pending tool-request file on
the operator's behalf; demonstrates the Concierge-request-filing
flow end-to-end. The backing service (N7 scope boundary, DECISIONS
`[2026-04-22 10:35]`) writes the .md file, updates the DB row, and
returns `RequestDetail`. It does NOT install the tool — that is X13
(if it ships) or manual operator work.

Input schema exposes all `NewRequestDraft` fields. Only `tool_name`
is required; the rest default to server-side null. MCP schema
defers enum validation to the backing service, matching the N7
router's shape.

Error-class mapping mirrors `concierge_recommend`:

- httpx connect/network/timeout → render_service_unavailable
- Non-2xx (including 409 filename collision) → render_service_error
- 2xx with malformed JSON or missing filename → render_malformed_response
- Unexpected exception → render_service_unavailable (defensive)
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from adapters.claude_code.dispatcher import ToolSpec
from adapters.claude_code.meta_tools import http_client, render


logger = logging.getLogger(__name__)


request_tool_spec = ToolSpec(
    name="concierge_request_tool",
    description=(
        "File a Concierge tool-request for operator review. Use when "
        "you noticed a capability gap, evaluated the options, and "
        "want a specific tool considered for the catalog. The "
        "request lands in Concierge's pending inbox; the operator "
        "approves / denies / defers. Do not block your current task "
        "waiting for approval — continue with existing tools."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "tool_name": {
                "type": "string",
                "description": "Display name of the tool you'd like Concierge to consider.",
            },
            "category": {
                "type": "string",
                "description": "Tool category (e.g. 'data-processing', 'text-processing').",
            },
            "install_method": {
                "type": "string",
                "description": "How the tool installs (e.g. 'npm -g', 'pip --user', 'single binary').",
            },
            "task_context": {
                "type": "string",
                "description": "What you were trying to do when you noticed the gap.",
            },
            "why_this_tool": {
                "type": "string",
                "description": "Why you think this specific tool fits the gap.",
            },
            "alternatives_considered": {
                "type": "string",
                "description": "Other tools you considered and why they were rejected.",
            },
            "risk_cost": {
                "type": "string",
                "description": "Install risk, cost, sudo requirements, license concerns.",
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "description": "Your confidence level in this recommendation.",
            },
            "is_discovered": {
                "type": "boolean",
                "description": "True if you discovered this via web search (vs. already knowing it).",
            },
            "source": {
                "type": "string",
                "description": "Where you found the tool (if discovered) — e.g. npm registry, awesome-list URL.",
            },
            "evidence": {
                "type": "string",
                "description": "Supporting evidence (stars, downloads, last commit, license).",
            },
        },
        "required": ["tool_name"],
    },
)


_KNOWN_FIELDS = (
    "tool_name",
    "category",
    "install_method",
    "task_context",
    "why_this_tool",
    "alternatives_considered",
    "risk_cost",
    "confidence",
    "is_discovered",
    "source",
    "evidence",
)


def _build_request_body(args: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {}
    for field in _KNOWN_FIELDS:
        if field in args and args[field] is not None:
            body[field] = args[field]
    return body


async def handle_request_tool(args: dict[str, Any]) -> dict[str, Any]:
    body = _build_request_body(args)
    client = http_client.get_client()
    try:
        response = await client.post("/requests", json=body)
    except (httpx.ConnectError, httpx.NetworkError, httpx.TimeoutException) as exc:
        logger.warning("concierge_request_tool.unavailable error=%s", exc)
        return render.error_result(
            render.render_service_unavailable(
                http_client.get_concierge_url(), f"{type(exc).__name__}: {exc}"
            )
        )
    except Exception as exc:
        logger.exception("concierge_request_tool.unexpected error=%s", exc)
        return render.error_result(
            render.render_service_unavailable(
                http_client.get_concierge_url(), f"{type(exc).__name__}: {exc}"
            )
        )

    if response.status_code >= 400:
        logger.warning(
            "concierge_request_tool.http_error status=%d", response.status_code
        )
        return render.error_result(
            render.render_service_error(response.status_code, response.text)
        )

    try:
        payload = response.json()
    except ValueError as exc:
        logger.warning("concierge_request_tool.malformed_json error=%s", exc)
        return render.error_result(
            render.render_malformed_response(f"response body is not valid JSON: {exc}")
        )

    if not isinstance(payload, dict) or "filename" not in payload:
        logger.warning("concierge_request_tool.malformed_shape missing=filename")
        return render.error_result(
            render.render_malformed_response(
                "response is missing the `filename` field"
            )
        )

    logger.info(
        "concierge_request_tool.ok filename=%s folder=%s",
        payload.get("filename"),
        payload.get("folder"),
    )
    return render.ok_result(render.render_request_tool_result(payload))
