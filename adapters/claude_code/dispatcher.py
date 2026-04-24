"""Method dispatcher — Layer 2 of the shim architecture.

An async registry: method name → handler. `initialize`,
`initialized`, `tools/list`, and `tools/call` are registered with
default built-in handlers at `build_default_dispatcher()` time.

The N11 Day-3 meta-tool handlers (`concierge_recommend`,
`concierge_request_tool`, `concierge_list_active`) register
onto this dispatcher — they augment `tools/list` (by extending
the list of advertised tools) and hook into `tools/call` (by
registering a per-tool handler). Day 2 ships the framework with
an **empty** tool list; N11 fills it.

Protocol version:
- We advertise `get_settings().claude_code_protocol_version` in the
  initialize response. Default `2025-11-25` (R1 closure — DECISIONS
  [2026-04-22 11:49] option iii: config-driven with current-client-
  tracking default). Override via `CONCIERGE_CLAUDE_CODE_PROTOCOL_VERSION`.
- If the client's requested version differs, we log an INFO notice
  and still respond with our advertised version. For clients that
  ACCEPT a version mismatch (non-hostile-handled), this works. For
  clients that REJECT older server versions (as real Claude Code
  2.1.117 does per the 2026-04-22 manual-verification finding), the
  default must match what the client sends — hence the config-driven
  surface.
- The value is read once at module import (i.e. shim startup).
  Mid-session env changes do not take effect until shim restart.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from adapters.claude_code.jsonrpc import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    JsonRpcRequest,
    make_error_response,
    make_result_response,
)
from core.config import get_settings


logger = logging.getLogger(__name__)


# MCP protocol version for the initialize response. Read from
# settings at module import time — see R1 closure comment in
# core/config.py for the env-override path.
PROTOCOL_VERSION = get_settings().claude_code_protocol_version
SERVER_NAME = "concierge-shim"
SERVER_VERSION = "0.1.0"


# A Handler takes the parsed params (dict/list/None) and returns
# the `result` value for the JSON-RPC response. Handlers may raise;
# the dispatcher catches and emits an INTERNAL_ERROR response.
Handler = Callable[[Optional[Any]], Awaitable[Any]]


# A ToolHandler takes a tools/call arguments dict and returns the
# tool-call result value (MCP's tools/call response shape). Kept
# separate from Handler because tools/call dispatch routes by tool
# name, not by JSON-RPC method name.
ToolHandler = Callable[[dict[str, Any]], Awaitable[Any]]


@dataclass
class ToolSpec:
    """One entry in the `tools/list` advertisement.

    Matches MCP's tool shape: name + description + JSON-Schema
    `inputSchema`. N11 registers meta-tool specs; this Day-2
    framework registers none.
    """

    name: str
    description: str
    input_schema: dict[str, Any]

    def to_mcp(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


@dataclass
class ResourceSpec:
    """One entry in the `resources/list` advertisement.

    Matches MCP's resource shape: `uri` + `name` + `description`
    + `mimeType`, plus the verbatim `text` body returned by
    `resources/read`. Fix Day 4 Task 2 uses this for the six
    prompt resources exposed under `concierge://prompts/{name}.md`.

    The `text` field is intentionally held in-memory: prompt
    fragments are small (a few KB each) and verbatim-sourced from
    Python constants, so loading them lazily from disk would add
    startup complexity without measurable benefit.
    """

    uri: str
    name: str
    description: str
    mime_type: str
    text: str

    def to_mcp(self) -> dict[str, Any]:
        """Shape for a `resources/list` entry — metadata only."""
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
        }

    def to_contents(self) -> dict[str, Any]:
        """Shape for one entry in a `resources/read` response's
        `contents` array — includes the verbatim body.
        """
        return {
            "uri": self.uri,
            "mimeType": self.mime_type,
            "text": self.text,
        }


@dataclass
class Dispatcher:
    _methods: dict[str, Handler] = field(default_factory=dict)
    _tools: dict[str, ToolSpec] = field(default_factory=dict)
    _tool_handlers: dict[str, ToolHandler] = field(default_factory=dict)
    _resources: dict[str, ResourceSpec] = field(default_factory=dict)
    _capabilities: dict[str, dict[str, Any]] = field(default_factory=dict)

    # ---- Registration --------------------------------------------------

    def register_method(self, name: str, handler: Handler) -> None:
        self._methods[name] = handler

    def register_tool(self, spec: ToolSpec, handler: ToolHandler) -> None:
        """Register a tool that will appear in `tools/list` and be
        callable via `tools/call`. N11 uses this for the three
        meta-tools Day 3.
        """
        self._tools[spec.name] = spec
        self._tool_handlers[spec.name] = handler

    def register_resource(self, spec: ResourceSpec) -> None:
        """Register a resource that will appear in `resources/list`
        and be readable via `resources/read`. Keyed by URI; re-
        registering the same URI replaces the prior spec.
        """
        self._resources[spec.uri] = spec

    def declare_capability(self, name: str, config: dict[str, Any]) -> None:
        """Declare an MCP capability advertised in the `initialize`
        response. `name` is the capability group (`"tools"`,
        `"resources"`); `config` is the sub-feature dict (empty
        `{}` for capabilities without sub-features).
        """
        self._capabilities[name] = config

    # ---- Introspection (used by default method handlers) --------------

    def list_tools(self) -> list[dict[str, Any]]:
        return [spec.to_mcp() for spec in self._tools.values()]

    def resolve_tool(self, name: str) -> Optional[ToolHandler]:
        return self._tool_handlers.get(name)

    def list_resources(self) -> list[dict[str, Any]]:
        return [spec.to_mcp() for spec in self._resources.values()]

    def resolve_resource(self, uri: str) -> Optional[ResourceSpec]:
        return self._resources.get(uri)

    def capabilities(self) -> dict[str, Any]:
        """Return a shallow copy of the current capability map for
        the `initialize` response. Copy so callers can't mutate
        state via the returned dict.
        """
        return dict(self._capabilities)

    # ---- Dispatch -----------------------------------------------------

    async def dispatch(self, request: JsonRpcRequest) -> Optional[dict[str, Any]]:
        """Route a parsed JsonRpcRequest to its handler. Returns the
        response dict (to serialize), or None for notifications.
        """
        if request.is_notification:
            # Notifications still get routed so the handler can
            # run side-effects; the return value is discarded.
            handler = self._methods.get(request.method)
            if handler is None:
                logger.debug(
                    "shim.notification unknown method=%s — ignored",
                    request.method,
                )
                return None
            try:
                await handler(request.params)
            except Exception as exc:
                logger.error(
                    "shim.notification handler raised method=%s error=%s: %s",
                    request.method,
                    type(exc).__name__,
                    exc,
                )
            return None

        handler = self._methods.get(request.method)
        if handler is None:
            logger.debug("shim.method_not_found method=%s id=%s", request.method, request.id)
            return make_error_response(
                request.id,
                METHOD_NOT_FOUND,
                f"method {request.method!r} is not registered",
            )
        try:
            result = await handler(request.params)
        except _ParamsError as exc:
            return make_error_response(
                request.id, INVALID_PARAMS, str(exc)
            )
        except Exception as exc:
            logger.exception(
                "shim.handler_raised method=%s id=%s error=%s",
                request.method,
                request.id,
                type(exc).__name__,
            )
            return make_error_response(
                request.id,
                INTERNAL_ERROR,
                f"handler for {request.method!r} raised {type(exc).__name__}: {exc}",
            )
        return make_result_response(request.id, result)


class _ParamsError(ValueError):
    """Handler-raised signal that params validation failed; the
    dispatcher converts this to an INVALID_PARAMS response so the
    error surface is distinct from INTERNAL_ERROR.
    """


# ---- Default built-in handlers ------------------------------------------


def build_default_dispatcher() -> Dispatcher:
    """Return a Dispatcher with the four MCP-required methods
    pre-registered:

      initialize     — handshake response with pinned protocol version
      initialized    — notification; ack-only
      tools/list     — returns advertised tools (empty on Day 2;
                       N11 fills it)
      tools/call     — routes to tool handler by name

    N11+ layers additional registrations onto this dispatcher
    without reconstructing it. Fix Day 4's narration-as-push
    pattern 2 adds the `resources` capability + two method
    handlers via `adapters.claude_code.resources.register_resources`.
    """
    d = Dispatcher()
    # Tools is the foundational capability; resources / prompts /
    # logging are additive and declared by their own registration
    # modules when active.
    d.declare_capability("tools", {})
    # Closures capture `d` so the handlers have introspection access
    # without importing the dispatcher module circularly.
    d.register_method("initialize", _make_handle_initialize(d))
    d.register_method("initialized", _handle_initialized)
    d.register_method("notifications/initialized", _handle_initialized)
    d.register_method("tools/list", _make_handle_tools_list(d))
    d.register_method("tools/call", _make_handle_tools_call(d))
    return d


def _make_handle_initialize(d: Dispatcher) -> Handler:
    """Build the `initialize` handler with a bound dispatcher so the
    advertised capabilities reflect whatever has been declared on
    `d` at call time (post-registration). This is why `initialize`
    must be registered AFTER the default tools capability is
    declared but BEFORE any `initialize` request arrives — the
    current ordering in `build_default_dispatcher` satisfies both.
    """

    async def _handle(params: Optional[Any]) -> dict[str, Any]:
        client_version = None
        if isinstance(params, dict):
            client_version = params.get("protocolVersion")
        if client_version and client_version != PROTOCOL_VERSION:
            logger.info(
                "shim.initialize protocol_mismatch client=%r shim=%r — "
                "responding with shim version; client decides whether to proceed",
                client_version,
                PROTOCOL_VERSION,
            )
        else:
            logger.info(
                "shim.initialize protocol=%s client_version=%r",
                PROTOCOL_VERSION,
                client_version,
            )
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": d.capabilities(),
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
            },
        }

    return _handle


async def _handle_initialized(params: Optional[Any]) -> None:
    """Client-side ack-notification after initialize. Per JSON-RPC
    + MCP, no response is expected; we log at DEBUG and return.
    """
    logger.debug("shim.initialized ack received")
    return None


def _make_handle_tools_list(d: Dispatcher) -> Handler:
    async def _handle(params: Optional[Any]) -> dict[str, Any]:
        tools = d.list_tools()
        logger.debug("shim.tools_list count=%d", len(tools))
        return {"tools": tools}

    return _handle


def _make_handle_tools_call(d: Dispatcher) -> Handler:
    async def _handle(params: Optional[Any]) -> dict[str, Any]:
        if not isinstance(params, dict):
            raise _ParamsError(
                f"tools/call expects an object params; got {type(params).__name__}"
            )
        tool_name = params.get("name")
        if not isinstance(tool_name, str) or not tool_name:
            raise _ParamsError("tools/call requires a non-empty string `name`")
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            raise _ParamsError(
                f"tools/call `arguments` must be an object; got {type(arguments).__name__}"
            )
        handler = d.resolve_tool(tool_name)
        if handler is None:
            # Per MCP, unknown-tool is an error INSIDE the tools/call
            # result (isError=True) rather than a JSON-RPC error.
            # Client UIs surface the difference. Day 2 ships empty
            # tools so every call hits this path.
            logger.debug("shim.tools_call unknown_tool=%s", tool_name)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"tool {tool_name!r} is not registered in this "
                            "Concierge shim instance"
                        ),
                    }
                ],
                "isError": True,
            }
        result = await handler(arguments)
        logger.debug("shim.tools_call name=%s ok", tool_name)
        return result

    return _handle
