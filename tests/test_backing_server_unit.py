"""Unit tests for N13 backing-server plumbing.

Fast suite — no subprocess spawning. Covers BackingServerSpec
validation, BackingServerRegistry registration (including the
prefix-collision invariant), find_by_tool_name routing logic, and
list_all_tools aggregation. Subprocess lifecycle tests live in
`tests/test_backing_server_integration.py` behind the `integration`
pytest marker.
"""
from __future__ import annotations

import pytest

from adapters.claude_code.backing_server import (
    BackingServer,
    BackingServerSpec,
    BackingToolSpec,
    PrefixCollisionError,
)
from adapters.claude_code.backing_server_registry import (
    BackingServerRegistry,
)


def _spec(
    *,
    name: str = "mock",
    prefix: str = "mock_",
    tools: list[BackingToolSpec] | None = None,
    command: list[str] | None = None,
) -> BackingServerSpec:
    if tools is None:
        tools = [
            BackingToolSpec(
                name=f"{prefix}ping",
                description="mock ping",
                input_schema={"type": "object", "properties": {}},
            )
        ]
    if command is None:
        command = ["echo", "nope"]
    return BackingServerSpec(
        name=name,
        tool_prefix=prefix,
        command=command,
        tool_inventory=tools,
    )


# ---- BackingServerSpec validation ----------------------------------------


class TestBackingServerSpec:
    def test_valid_spec_constructs(self):
        spec = _spec()
        assert spec.name == "mock"
        assert spec.tool_prefix == "mock_"
        assert len(spec.tool_inventory) == 1

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="name"):
            BackingServerSpec(
                name="",
                tool_prefix="mock_",
                command=["echo"],
                tool_inventory=[
                    BackingToolSpec(name="mock_x", description="", input_schema={})
                ],
            )

    def test_empty_prefix_rejected(self):
        with pytest.raises(ValueError, match="tool_prefix"):
            BackingServerSpec(
                name="mock",
                tool_prefix="",
                command=["echo"],
                tool_inventory=[],
            )

    def test_empty_command_rejected(self):
        with pytest.raises(ValueError, match="command"):
            BackingServerSpec(
                name="mock",
                tool_prefix="mock_",
                command=[],
                tool_inventory=[],
            )

    def test_tool_not_starting_with_prefix_rejected(self):
        with pytest.raises(ValueError, match="does not start with tool_prefix"):
            BackingServerSpec(
                name="mock",
                tool_prefix="mock_",
                command=["echo"],
                tool_inventory=[
                    BackingToolSpec(
                        name="other_tool",  # doesn't start with "mock_"
                        description="",
                        input_schema={},
                    )
                ],
            )


class TestBackingToolSpec:
    def test_to_mcp_shape(self):
        t = BackingToolSpec(
            name="mock_ping",
            description="mock",
            input_schema={"type": "object", "properties": {}},
        )
        mcp = t.to_mcp()
        assert mcp == {
            "name": "mock_ping",
            "description": "mock",
            "inputSchema": {"type": "object", "properties": {}},
        }


# ---- Registry registration -----------------------------------------------


class TestBackingServerRegistry:
    def test_empty_registry_has_no_tools(self):
        registry = BackingServerRegistry()
        assert len(registry) == 0
        assert registry.list_all_tools() == []

    def test_register_adds_backing_server(self):
        registry = BackingServerRegistry()
        server = registry.register(_spec())
        assert isinstance(server, BackingServer)
        assert len(registry) == 1
        assert "mock_" in registry.registered_prefixes()

    def test_register_aggregates_tool_inventory_into_list_all_tools(self):
        registry = BackingServerRegistry()
        registry.register(
            _spec(
                name="mock-a",
                prefix="a_",
                tools=[
                    BackingToolSpec(name="a_one", description="", input_schema={}),
                    BackingToolSpec(name="a_two", description="", input_schema={}),
                ],
            )
        )
        registry.register(
            _spec(
                name="mock-b",
                prefix="b_",
                tools=[
                    BackingToolSpec(name="b_one", description="", input_schema={}),
                ],
            )
        )
        names = {t["name"] for t in registry.list_all_tools()}
        assert names == {"a_one", "a_two", "b_one"}

    def test_prefix_collision_on_register_raises(self):
        """Critical invariant — two specs with the same tool_prefix
        would create "which backing server serves this tool?" ambiguity
        at runtime. Fail loud at registration time.
        """
        registry = BackingServerRegistry()
        registry.register(_spec(name="first", prefix="shared_"))
        with pytest.raises(PrefixCollisionError, match="shared_"):
            registry.register(
                _spec(
                    name="second",
                    prefix="shared_",
                    tools=[
                        BackingToolSpec(
                            name="shared_tool", description="", input_schema={}
                        )
                    ],
                )
            )
        # First registration is intact
        assert len(registry) == 1
        assert registry.registered_prefixes() == ["shared_"]


# ---- Prefix-based lookup -------------------------------------------------


class TestFindByToolName:
    def test_matching_prefix_returns_server(self):
        registry = BackingServerRegistry()
        registry.register(_spec(name="mock", prefix="mock_"))
        found = registry.find_by_tool_name("mock_ping")
        assert found is not None
        assert found.spec.name == "mock"

    def test_non_matching_prefix_returns_none(self):
        registry = BackingServerRegistry()
        registry.register(_spec(name="mock", prefix="mock_"))
        assert registry.find_by_tool_name("other_ping") is None
        assert registry.find_by_tool_name("concierge_recommend") is None

    def test_longest_prefix_wins_for_overlapping_prefixes(self):
        """Defensive for future specs that might register overlapping
        prefixes (e.g. `firefox_` + `firefox_devtools_`). The more-
        specific prefix should win.
        """
        registry = BackingServerRegistry()
        registry.register(
            _spec(
                name="firefox",
                prefix="firefox_",
                tools=[
                    BackingToolSpec(
                        name="firefox_ping", description="", input_schema={}
                    )
                ],
            )
        )
        registry.register(
            _spec(
                name="firefox-devtools",
                prefix="firefox_devtools_",
                tools=[
                    BackingToolSpec(
                        name="firefox_devtools_inspect",
                        description="",
                        input_schema={},
                    )
                ],
            )
        )
        # Short prefix: firefox server
        ping = registry.find_by_tool_name("firefox_ping")
        assert ping is not None and ping.spec.name == "firefox"
        # Long prefix: devtools server (more specific wins)
        inspect = registry.find_by_tool_name("firefox_devtools_inspect")
        assert inspect is not None and inspect.spec.name == "firefox-devtools"

    def test_empty_registry_returns_none(self):
        registry = BackingServerRegistry()
        assert registry.find_by_tool_name("anything") is None


# ---- Shutdown (empty registry path) --------------------------------------


class TestShutdownEmpty:
    @pytest.mark.asyncio
    async def test_shutdown_all_on_empty_registry_is_noop(self):
        registry = BackingServerRegistry()
        await registry.shutdown_all()  # Must not raise

    @pytest.mark.asyncio
    async def test_shutdown_all_skips_unspawned_servers(self):
        """A registered-but-never-spawned BackingServer has proc=None;
        stop() must be a no-op and not raise.
        """
        registry = BackingServerRegistry()
        registry.register(_spec())
        await registry.shutdown_all()  # Must not raise


# ---- Dispatcher integration (unit level, no subprocess) -----------------


class TestDispatcherIntegrationUnit:
    """Verify install_backing_server_routing wires the registry into
    the dispatcher's tools/list and tools/call handlers. No backing
    server is actually spawned — we register a spec but never trigger
    tool-calls against it. Subprocess end-to-end is tested in the
    integration suite.
    """

    def test_install_replaces_default_tools_list_handler(self):
        from adapters.claude_code.backing_server_registry import (
            install_backing_server_routing,
        )
        from adapters.claude_code.dispatcher import build_default_dispatcher

        dispatcher = build_default_dispatcher()
        registry = BackingServerRegistry()
        registry.register(_spec())
        install_backing_server_routing(dispatcher, registry)

        # The `tools/list` handler is now the registry-aware one;
        # registered via `register_method` so it replaces the default.
        assert "tools/list" in dispatcher._methods

    @pytest.mark.asyncio
    async def test_tools_list_aggregates_meta_and_backing(self):
        from adapters.claude_code.backing_server_registry import (
            install_backing_server_routing,
        )
        from adapters.claude_code.dispatcher import build_default_dispatcher
        from adapters.claude_code.jsonrpc import JsonRpcRequest
        from adapters.claude_code.meta_tools import register_meta_tools

        dispatcher = build_default_dispatcher()
        register_meta_tools(dispatcher)  # 3 meta-tools
        registry = BackingServerRegistry()
        registry.register(
            _spec(
                name="mock",
                prefix="mock_",
                tools=[
                    BackingToolSpec(name="mock_ping", description="", input_schema={}),
                    BackingToolSpec(name="mock_echo", description="", input_schema={}),
                ],
            )
        )
        install_backing_server_routing(dispatcher, registry)

        req = JsonRpcRequest(
            method="tools/list", params=None, id=1, is_notification=False
        )
        resp = await dispatcher.dispatch(req)
        tool_names = {t["name"] for t in resp["result"]["tools"]}

        # Meta-tools still present
        assert "concierge_recommend" in tool_names
        assert "concierge_request_tool" in tool_names
        assert "concierge_list_active" in tool_names
        # Backing-server tools also present (pre-declared inventory;
        # no subprocess spawned)
        assert "mock_ping" in tool_names
        assert "mock_echo" in tool_names

    @pytest.mark.asyncio
    async def test_tools_call_unknown_tool_returns_mcp_error_not_rpc_error(self):
        """Prefix-match misses, meta-tool lookup misses — unknown
        tool returns isError=True result, not a JSON-RPC error.
        Matches the default handler's contract.
        """
        from adapters.claude_code.backing_server_registry import (
            install_backing_server_routing,
        )
        from adapters.claude_code.dispatcher import build_default_dispatcher
        from adapters.claude_code.jsonrpc import JsonRpcRequest

        dispatcher = build_default_dispatcher()
        registry = BackingServerRegistry()
        install_backing_server_routing(dispatcher, registry)

        req = JsonRpcRequest(
            method="tools/call",
            params={"name": "unregistered_tool", "arguments": {}},
            id=2,
            is_notification=False,
        )
        resp = await dispatcher.dispatch(req)
        assert "result" in resp
        assert resp["result"]["isError"] is True
        assert "Unknown tool" in resp["result"]["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_tools_call_bad_params_still_returns_invalid_params(self):
        """Param validation (missing `name`, etc.) must surface as
        JSON-RPC INVALID_PARAMS — not swallowed by the new handler.
        """
        from adapters.claude_code.backing_server_registry import (
            install_backing_server_routing,
        )
        from adapters.claude_code.dispatcher import build_default_dispatcher
        from adapters.claude_code.jsonrpc import INVALID_PARAMS, JsonRpcRequest

        dispatcher = build_default_dispatcher()
        registry = BackingServerRegistry()
        install_backing_server_routing(dispatcher, registry)

        req = JsonRpcRequest(
            method="tools/call",
            params={"arguments": {}},  # missing `name`
            id=3,
            is_notification=False,
        )
        resp = await dispatcher.dispatch(req)
        assert "error" in resp
        assert resp["error"]["code"] == INVALID_PARAMS
