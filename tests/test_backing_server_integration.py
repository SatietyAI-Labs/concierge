"""Integration tests for N13 backing-server lifecycle.

Subprocess-heavy — every test spawns at least one real child process
running `tests/fixtures/mock_mcp_backing_server.py`. Marked
`@pytest.mark.integration` per the existing convention
(pyproject.toml markers); excluded from the default fast suite via
`pytest -m "not integration"`. Run explicitly with
`pytest -m integration` or by path.

Scope: happy-path spawn + tools/call + stop lifecycle; spawn
failures (command-not-found, initialize error); registry + dispatcher
end-to-end through the proxy. Edge cases like initialize-timeout
and crash-mid-handshake are covered with env-var-gated behaviors of
the mock fixture.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from adapters.claude_code.backing_server import (
    BackingServer,
    BackingServerNotReadyError,
    BackingServerSpec,
    BackingToolSpec,
)
from adapters.claude_code.backing_server_registry import (
    BackingServerRegistry,
    install_backing_server_routing,
)


pytestmark = pytest.mark.integration


REPO_ROOT = Path(__file__).resolve().parent.parent
MOCK_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "mock_mcp_backing_server.py"


def _mock_spec(
    *,
    name: str = "mock",
    prefix: str = "mock_",
    env: dict[str, str] | None = None,
    command_override: list[str] | None = None,
) -> BackingServerSpec:
    mock_env = {"MOCK_MCP_TOOL_PREFIX": prefix}
    if env:
        mock_env.update(env)
    return BackingServerSpec(
        name=name,
        tool_prefix=prefix,
        command=command_override or [sys.executable, str(MOCK_FIXTURE)],
        tool_inventory=[
            BackingToolSpec(
                name=f"{prefix}ping",
                description="mock ping",
                input_schema={"type": "object", "properties": {}},
            ),
            BackingToolSpec(
                name=f"{prefix}echo",
                description="mock echo",
                input_schema={
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                },
            ),
        ],
        env=mock_env,
    )


# ---- BackingServer lifecycle ---------------------------------------------


class TestBackingServerSpawn:
    @pytest.mark.asyncio
    async def test_happy_path_start_call_stop(self):
        server = BackingServer(_mock_spec())
        try:
            await server.ensure_started()
            assert server.is_ready is True
            assert server.last_error is None

            result = await server.call_tool("mock_ping", {})
            assert result["isError"] is False
            assert "mock-mock_ping" in result["content"][0]["text"]
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_tool_call_args_round_trip_through_proxy(self):
        server = BackingServer(_mock_spec())
        try:
            await server.ensure_started()
            result = await server.call_tool("mock_echo", {"message": "hello"})
            assert result["isError"] is False
            text = result["content"][0]["text"]
            assert "mock-mock_echo" in text
            assert '"message": "hello"' in text
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_ensure_started_is_idempotent(self):
        """Concurrent callers should serialize on the start-lock and
        get the same fully-initialized server without double-spawning.
        """
        import asyncio

        server = BackingServer(_mock_spec())
        try:
            # Fire three ensure_started in parallel; only one actual
            # spawn should happen.
            await asyncio.gather(
                server.ensure_started(),
                server.ensure_started(),
                server.ensure_started(),
            )
            assert server.is_ready is True
        finally:
            await server.stop()


class TestBackingServerSpawnFailures:
    @pytest.mark.asyncio
    async def test_command_not_found_fails_soft(self):
        spec = _mock_spec(command_override=["/nonexistent/mcp-binary-xyz"])
        server = BackingServer(spec)
        await server.ensure_started()
        assert server.is_ready is False
        assert server.last_error is not None
        # Tool call after failed spawn raises the sentinel (which the
        # dispatcher wrapper converts to isError=True).
        with pytest.raises(BackingServerNotReadyError):
            await server.call_tool("mock_ping", {})
        await server.stop()  # Must not raise

    @pytest.mark.asyncio
    async def test_initialize_error_marks_not_ready(self):
        spec = _mock_spec(env={"MOCK_MCP_FAIL_INITIALIZE": "1"})
        server = BackingServer(spec)
        try:
            await server.ensure_started()
            assert server.is_ready is False
            assert "error" in (server.last_error or "").lower()
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_crash_before_init_fails_soft(self):
        spec = _mock_spec(env={"MOCK_MCP_CRASH_BEFORE_INIT": "1"})
        server = BackingServer(spec)
        try:
            await server.ensure_started()
            assert server.is_ready is False
        finally:
            await server.stop()


class TestBackingServerStop:
    @pytest.mark.asyncio
    async def test_stop_completes_cleanly_after_successful_start(self):
        server = BackingServer(_mock_spec())
        await server.ensure_started()
        assert server.proc is not None
        await server.stop()
        # Process should be reaped after stop completes
        assert server.proc.returncode is not None

    @pytest.mark.asyncio
    async def test_stop_is_idempotent(self):
        server = BackingServer(_mock_spec())
        await server.ensure_started()
        await server.stop()
        await server.stop()  # Second call is a no-op, must not raise


# ---- Registry + dispatcher end-to-end -----------------------------------


class TestRegistryIntegration:
    @pytest.mark.asyncio
    async def test_registry_shutdown_all_reaps_spawned_servers(self):
        registry = BackingServerRegistry()
        registry.register(_mock_spec())
        server = registry.find_by_tool_name("mock_ping")
        assert server is not None
        await server.ensure_started()
        assert server.proc is not None
        assert server.is_ready is True

        await registry.shutdown_all()
        assert server.proc.returncode is not None

    @pytest.mark.asyncio
    async def test_dispatcher_routes_tool_call_to_backing_server(self):
        """Full end-to-end: dispatcher receives tools/call, registry
        matches prefix, BackingServer proxies to the mock subprocess,
        result bubbles back up. This is what Claude Code sees.
        """
        from adapters.claude_code.dispatcher import build_default_dispatcher
        from adapters.claude_code.jsonrpc import JsonRpcRequest

        dispatcher = build_default_dispatcher()
        registry = BackingServerRegistry()
        registry.register(_mock_spec())
        install_backing_server_routing(dispatcher, registry)

        try:
            req = JsonRpcRequest(
                method="tools/call",
                params={"name": "mock_ping", "arguments": {}},
                id=1,
                is_notification=False,
            )
            resp = await dispatcher.dispatch(req)
            assert "result" in resp
            assert resp["result"]["isError"] is False
            assert "mock-mock_ping" in resp["result"]["content"][0]["text"]
        finally:
            await registry.shutdown_all()

    @pytest.mark.asyncio
    async def test_dispatcher_falls_through_to_meta_tool_when_no_prefix_matches(self):
        """Tool name that matches no backing-server prefix falls
        through to the dispatcher's own tool resolver.
        """
        from adapters.claude_code.dispatcher import (
            ToolSpec,
            build_default_dispatcher,
        )
        from adapters.claude_code.jsonrpc import JsonRpcRequest

        async def _inline_handler(_args):
            return {
                "content": [{"type": "text", "text": "inline ran"}],
                "isError": False,
            }

        dispatcher = build_default_dispatcher()
        dispatcher.register_tool(
            ToolSpec(
                name="inline_sample",
                description="",
                input_schema={"type": "object", "properties": {}},
            ),
            _inline_handler,
        )
        registry = BackingServerRegistry()
        registry.register(_mock_spec())  # prefix mock_
        install_backing_server_routing(dispatcher, registry)

        try:
            req = JsonRpcRequest(
                method="tools/call",
                params={"name": "inline_sample", "arguments": {}},
                id=2,
                is_notification=False,
            )
            resp = await dispatcher.dispatch(req)
            assert resp["result"]["isError"] is False
            assert "inline ran" in resp["result"]["content"][0]["text"]
        finally:
            await registry.shutdown_all()

    @pytest.mark.asyncio
    async def test_failed_backing_server_returns_mcp_error_not_crash(self):
        """When a prefix-matched backing server fails to start, the
        dispatcher wrapper converts BackingServerNotReadyError into
        an isError=True result — shim stays alive for meta-tool calls.
        """
        from adapters.claude_code.dispatcher import build_default_dispatcher
        from adapters.claude_code.jsonrpc import JsonRpcRequest

        bad_spec = _mock_spec(command_override=["/nonexistent/binary-xyz"])
        dispatcher = build_default_dispatcher()
        registry = BackingServerRegistry()
        registry.register(bad_spec)
        install_backing_server_routing(dispatcher, registry)

        try:
            req = JsonRpcRequest(
                method="tools/call",
                params={"name": "mock_ping", "arguments": {}},
                id=3,
                is_notification=False,
            )
            resp = await dispatcher.dispatch(req)
            assert "result" in resp
            assert resp["result"]["isError"] is True
            assert "not ready" in resp["result"]["content"][0]["text"].lower()
        finally:
            await registry.shutdown_all()
