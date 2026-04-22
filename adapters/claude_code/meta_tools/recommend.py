"""concierge_recommend meta-tool — backs on POST /recommend (N6).

Highest-priority N11 meta-tool per the Day-3-morning priority order
(concierge_recommend > concierge_request_tool > concierge_list_active).
N12 gap-report injection (Day 3 midday) depends on this handler's
output shape; N14 integration smoke drives this handler end-to-end.

Input schema exposes the four fields `RecommendRequest` accepts
(task required, cwd / task_hint / active_tools optional). The
handler forwards them directly as the POST body — no field
substitution, no defaulting, no client-side validation beyond what
MCP's own schema validation provides.

Error-class mapping (per `render.py` contract):

- `httpx.ConnectError` / `httpx.NetworkError` / `httpx.TimeoutException`
  → `render_service_unavailable(...)` with the base URL and exception
  detail.
- Non-2xx HTTP status → `render_service_error(status, body)`.
- 2xx with malformed JSON or missing required fields →
  `render_malformed_response(detail)`.
- Unexpected exception → `render_service_unavailable(...)` with the
  exception class name, so the shim never crashes on handler failure.

All error results are returned with `isError=True` so the MCP client
can surface them distinctly from success cases. Handler exceptions
never propagate — the dispatcher-level INTERNAL_ERROR path is
reserved for genuinely unrecoverable states.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from adapters.claude_code.dispatcher import ToolSpec
from adapters.claude_code.meta_tools import http_client, render


logger = logging.getLogger(__name__)


recommend_spec = ToolSpec(
    name="concierge_recommend",
    description=(
        "Ask Concierge to recommend tools for a task. Concierge "
        "consults its catalog, memory of prior tool decisions, and "
        "discovery heuristics, then returns a ranked list with "
        "rationale and confidence. Use when you notice a capability "
        "gap or want to verify you are reaching for the right tool."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Natural-language description of the task you're trying to accomplish.",
            },
            "cwd": {
                "type": "string",
                "description": "Your current working directory, if relevant.",
            },
            "task_hint": {
                "type": "string",
                "description": "Optional category hint (e.g. 'data-analysis', 'content-drafting').",
            },
            "active_tools": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tool slugs already active in your session; Concierge prefers recommendations that leverage these.",
            },
        },
        "required": ["task"],
    },
)


def _build_request_body(args: dict[str, Any]) -> dict[str, Any]:
    """Select known fields from the MCP args dict. MCP's schema
    validation will have rejected completely-malformed args before
    we see them; defense-in-depth here only pulls through documented
    fields.
    """
    body: dict[str, Any] = {"task": args.get("task", "")}
    if "cwd" in args and args["cwd"] is not None:
        body["cwd"] = args["cwd"]
    if "task_hint" in args and args["task_hint"] is not None:
        body["task_hint"] = args["task_hint"]
    if "active_tools" in args and args["active_tools"] is not None:
        body["active_tools"] = args["active_tools"]
    return body


async def handle_recommend(args: dict[str, Any]) -> dict[str, Any]:
    """concierge_recommend handler — POST /recommend, render markdown."""
    body = _build_request_body(args)
    client = http_client.get_client()
    try:
        response = await client.post("/recommend", json=body)
    except (httpx.ConnectError, httpx.NetworkError, httpx.TimeoutException) as exc:
        logger.warning("concierge_recommend.unavailable error=%s", exc)
        return render.error_result(
            render.render_service_unavailable(
                http_client.get_concierge_url(), f"{type(exc).__name__}: {exc}"
            )
        )
    except Exception as exc:  # defensive: never crash the shim
        logger.exception("concierge_recommend.unexpected error=%s", exc)
        return render.error_result(
            render.render_service_unavailable(
                http_client.get_concierge_url(), f"{type(exc).__name__}: {exc}"
            )
        )

    if response.status_code >= 400:
        logger.warning(
            "concierge_recommend.http_error status=%d", response.status_code
        )
        return render.error_result(
            render.render_service_error(response.status_code, response.text)
        )

    try:
        payload = response.json()
    except ValueError as exc:
        logger.warning("concierge_recommend.malformed_json error=%s", exc)
        return render.error_result(
            render.render_malformed_response(f"response body is not valid JSON: {exc}")
        )

    if not isinstance(payload, dict) or "recommendations" not in payload:
        logger.warning("concierge_recommend.malformed_shape missing=recommendations")
        return render.error_result(
            render.render_malformed_response(
                "response is missing the `recommendations` field"
            )
        )

    logger.info(
        "concierge_recommend.ok memory_available=%s recs=%d model=%s",
        payload.get("memory_available"),
        len(payload.get("recommendations", []) or []),
        payload.get("model"),
    )
    return render.ok_result(render.render_recommend_result(payload))
