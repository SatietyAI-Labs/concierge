"""concierge_list_active meta-tool — backs on GET /tools.

Third-priority N11 meta-tool. Cut 3 deferrable per build-plan §F.2.3
(drops the registration line in `meta_tools/__init__.py` and this
module). Its job is to give a Claude Code session visibility into
the current Concierge catalog: what is active, what is dormant
(in-manifest but not active), and how tools are grouped by pack.

By default the handler filters to `is_active=True`. If the caller
passes `dormant=true`, the filter flips to `is_in_manifest=True AND
is_active=False` per the endpoint's `dormant` convenience filter.

Error-class mapping mirrors `concierge_recommend`.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from adapters.claude_code.dispatcher import ToolSpec
from adapters.claude_code.meta_tools import http_client, render


logger = logging.getLogger(__name__)


list_active_spec = ToolSpec(
    name="concierge_list_active",
    description=(
        "List tools currently active in Concierge's catalog, "
        "grouped by pack. Use for a quick inventory before asking "
        "for recommendations or filing a request — avoids "
        "duplicating something Concierge already knows about. "
        "Pass `dormant=true` to see in-manifest-but-not-active "
        "tools instead (candidates for activation)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "Filter to one category (e.g. 'data-processing').",
            },
            "pack_slug": {
                "type": "string",
                "description": "Filter to one pack slug.",
            },
            "dormant": {
                "type": "boolean",
                "description": "If true, list in-manifest-but-inactive tools instead of active ones.",
            },
        },
    },
)


def _build_query_params(args: dict[str, Any]) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if args.get("dormant") is True:
        params["dormant"] = "true"
    else:
        params["is_active"] = "true"
    if args.get("category"):
        params["category"] = args["category"]
    if args.get("pack_slug"):
        params["pack_slug"] = args["pack_slug"]
    params["limit"] = 1000  # meta-tool users want the full set, not pagination
    return params


async def handle_list_active(args: dict[str, Any]) -> dict[str, Any]:
    params = _build_query_params(args)
    client = http_client.get_client()
    try:
        response = await client.get("/tools", params=params)
    except httpx.TimeoutException as exc:
        logger.warning(
            "concierge_list_active.timeout error=%s timeout_s=%s",
            exc,
            http_client.DEFAULT_TIMEOUT_SECONDS,
        )
        return render.error_result(
            render.render_service_timeout(
                http_client.get_concierge_url(),
                f"{type(exc).__name__}: {exc}",
                http_client.DEFAULT_TIMEOUT_SECONDS,
            )
        )
    except (httpx.ConnectError, httpx.NetworkError) as exc:
        logger.warning("concierge_list_active.unavailable error=%s", exc)
        return render.error_result(
            render.render_service_unavailable(
                http_client.get_concierge_url(), f"{type(exc).__name__}: {exc}"
            )
        )
    except Exception as exc:
        logger.exception("concierge_list_active.unexpected error=%s", exc)
        return render.error_result(
            render.render_service_unavailable(
                http_client.get_concierge_url(), f"{type(exc).__name__}: {exc}"
            )
        )

    if response.status_code >= 400:
        logger.warning(
            "concierge_list_active.http_error status=%d", response.status_code
        )
        return render.error_result(
            render.render_service_error(response.status_code, response.text)
        )

    try:
        payload = response.json()
    except ValueError as exc:
        logger.warning("concierge_list_active.malformed_json error=%s", exc)
        return render.error_result(
            render.render_malformed_response(f"response body is not valid JSON: {exc}")
        )

    if not isinstance(payload, dict) or "items" not in payload:
        logger.warning("concierge_list_active.malformed_shape missing=items")
        return render.error_result(
            render.render_malformed_response(
                "response is missing the `items` field"
            )
        )

    logger.info(
        "concierge_list_active.ok items=%d dormant=%s",
        len(payload.get("items", []) or []),
        args.get("dormant") is True,
    )
    return render.ok_result(render.render_list_active_result(payload))
