"""N13 — BackingServerRegistry + dispatcher integration glue.

Holds BackingServer instances keyed by `tool_prefix`. Provides the
prefix-based routing surface the dispatcher's `tools/call` handler
consults; aggregates backing-server tool inventories into
`tools/list` responses.

See `backing_server.py` for lifecycle details. This module is
purely the coordination layer — it holds the registry state and
the install-into-dispatcher helper.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from adapters.claude_code.backing_server import (
    BackingServer,
    BackingServerNotReadyError,
    BackingServerSpec,
    PrefixCollisionError,
)
from adapters.claude_code.dispatcher import Dispatcher, _ParamsError


logger = logging.getLogger(__name__)


class BackingServerRegistry:
    """Registry of BackingServer instances by `tool_prefix`.

    V1 is empty-by-default; registration is programmatic and happens
    during shim `main()` composition (though no backing servers are
    registered at build time — the registry is plumbing).

    Thread-safety: owned by a single event loop. No locking beyond
    what `BackingServer` provides internally.
    """

    def __init__(self) -> None:
        self._servers: dict[str, BackingServer] = {}

    # ---- Registration ------------------------------------------------

    def register(self, spec: BackingServerSpec) -> BackingServer:
        """Register a backing server. Returns the spawned-lazy
        BackingServer instance. Raises PrefixCollisionError if
        `spec.tool_prefix` is already registered — silent overwrite
        would create routing ambiguity at runtime.
        """
        if spec.tool_prefix in self._servers:
            existing = self._servers[spec.tool_prefix]
            raise PrefixCollisionError(
                f"tool_prefix {spec.tool_prefix!r} already registered "
                f"to backing server {existing.spec.name!r}; cannot "
                f"also register {spec.name!r}"
            )
        server = BackingServer(spec)
        self._servers[spec.tool_prefix] = server
        logger.info(
            "backing_server.register name=%s prefix=%s tools=%d",
            spec.name,
            spec.tool_prefix,
            len(spec.tool_inventory),
        )
        return server

    # ---- Lookup + routing -------------------------------------------

    def find_by_tool_name(self, tool_name: str) -> Optional[BackingServer]:
        """Return the backing server whose prefix matches the given
        tool name, or None if no prefix matches. Longest-prefix wins
        if multiple prefixes happen to match (defensive against a
        future prefix pattern like `firefox_` + `firefox_devtools_`).
        """
        best: Optional[BackingServer] = None
        for prefix, server in self._servers.items():
            if tool_name.startswith(prefix):
                if best is None or len(prefix) > len(best.spec.tool_prefix):
                    best = server
        return best

    def list_all_tools(self) -> list[dict[str, Any]]:
        """Aggregate pre-declared tool inventories from every
        registered backing server into MCP-shaped dicts suitable
        for the tools/list response. No spawning — the inventory
        is declared on each spec (see backing_server.py module
        docstring for rationale).
        """
        tools: list[dict[str, Any]] = []
        for server in self._servers.values():
            for t in server.spec.tool_inventory:
                tools.append(t.to_mcp())
        return tools

    # ---- Lifecycle --------------------------------------------------

    async def unload(self, tool_prefix: str) -> bool:
        """Tear down a single registered backing server by prefix.

        Symmetric with `register(spec)`. Per Fix Day 3 Task 5, this is
        the Claude Code loader's unload surface — the checkpoint
        criterion ("unload('csvkit') removes csvkit from active and
        frees resources") maps to: find the server, call its async
        stop() (graceful stdin-close → SIGTERM → SIGKILL cascade per
        backing_server.stop), remove from the registry dict.

        Returns True if a server was found and unloaded, False if no
        server was registered under the given prefix.

        Stop() is safe to call before start(); a never-spawned server
        unloads cleanly without issuing any SIGTERM/SIGKILL.
        """
        server = self._servers.get(tool_prefix)
        if server is None:
            logger.info(
                "backing_server.unload_miss prefix=%s — not registered",
                tool_prefix,
            )
            return False

        try:
            await server.stop()
        except Exception as exc:
            logger.warning(
                "backing_server.unload_error name=%s prefix=%s error=%s",
                server.spec.name, tool_prefix, exc,
            )
            # Continue to remove from registry — a leaked subprocess
            # is a worse outcome than a leaked process that might get
            # retried on restart.
        del self._servers[tool_prefix]
        logger.info(
            "backing_server.unload name=%s prefix=%s",
            server.spec.name, tool_prefix,
        )
        return True

    async def shutdown_all(self) -> None:
        """Tear down every registered backing server. Called from the
        shim's `main()` finally block alongside the http-client
        aclose. Safe when no backing servers were ever spawned
        (ensure_started gates on spawn_attempted).
        """
        for server in self._servers.values():
            try:
                await server.stop()
            except Exception as exc:
                logger.warning(
                    "backing_server.shutdown_error name=%s error=%s",
                    server.spec.name,
                    exc,
                )

    # ---- Introspection (test-only) ----------------------------------

    def __len__(self) -> int:
        return len(self._servers)

    def registered_prefixes(self) -> list[str]:
        return list(self._servers.keys())


# ---- Dispatcher integration -----------------------------------------


def install_backing_server_routing(
    dispatcher: Dispatcher,
    registry: BackingServerRegistry,
) -> None:
    """Wire a BackingServerRegistry into an existing Dispatcher by
    replacing the built-in `tools/list` and `tools/call` handlers
    with ones that also consult the registry.

    Must be called AFTER `build_default_dispatcher()` and AFTER
    `register_meta_tools(dispatcher)` — meta-tools remain the
    fallthrough path when no backing-server prefix matches.
    """

    async def _handle_tools_list(_params):
        meta_tools = dispatcher.list_tools()
        backing_tools = registry.list_all_tools()
        # Meta-tools first (priority order per N11), backing-server
        # tools after. Claude Code client sees a single flat list.
        return {"tools": meta_tools + backing_tools}

    async def _handle_tools_call(params):
        # Mirror the default handler's param-validation shape so the
        # dispatcher's existing `_ParamsError` → INVALID_PARAMS
        # translation applies unchanged.
        if not isinstance(params, dict):
            raise _ParamsError(
                f"tools/call expects an object params; got {type(params).__name__}"
            )
        tool_name = params.get("name")
        if not isinstance(tool_name, str) or not tool_name:
            raise _ParamsError(
                "tools/call requires a non-empty string `name`"
            )
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            raise _ParamsError(
                f"tools/call `arguments` must be an object; got {type(arguments).__name__}"
            )

        # Prefix match first — backing servers take precedence when
        # their prefix matches, even if a meta-tool happens to share
        # the same name (not expected, but deterministic).
        backing = registry.find_by_tool_name(tool_name)
        if backing is not None:
            try:
                return await backing.call_tool(tool_name, arguments)
            except BackingServerNotReadyError as exc:
                logger.warning(
                    "backing_server.not_ready name=%s tool=%s error=%s",
                    backing.spec.name,
                    tool_name,
                    exc,
                )
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"Backing server {backing.spec.name!r} "
                                f"is not ready: {exc}"
                            ),
                        }
                    ],
                    "isError": True,
                }
            except Exception as exc:
                # Defensive: never crash the shim on a backing-server
                # error. Convert to isError=True MCP response.
                logger.exception(
                    "backing_server.unexpected name=%s tool=%s error=%s",
                    backing.spec.name,
                    tool_name,
                    exc,
                )
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"Backing server {backing.spec.name!r} "
                                f"raised an unexpected error: {type(exc).__name__}: {exc}"
                            ),
                        }
                    ],
                    "isError": True,
                }

        # No prefix match → fall through to meta-tool handler
        handler = dispatcher.resolve_tool(tool_name)
        if handler is None:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Unknown tool: {tool_name!r}",
                    }
                ],
                "isError": True,
            }
        return await handler(arguments)

    dispatcher.register_method("tools/list", _handle_tools_list)
    dispatcher.register_method("tools/call", _handle_tools_call)
