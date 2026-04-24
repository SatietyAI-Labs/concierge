"""Tests for adapters.claude_code.dispatcher — Layer 2 method
registry + default built-in handlers.

In-process async tests; no subprocess, no stdio. Drives the
dispatcher with crafted `JsonRpcRequest` objects and asserts
response shapes.
"""
from __future__ import annotations

import logging

import pytest

from adapters.claude_code.dispatcher import (
    PROTOCOL_VERSION,
    SERVER_NAME,
    SERVER_VERSION,
    Dispatcher,
    ToolSpec,
    build_default_dispatcher,
)
from adapters.claude_code.jsonrpc import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    JsonRpcRequest,
)


# ---- Built-in handlers --------------------------------------------------


@pytest.mark.asyncio
async def test_initialize_response_pins_protocol_version():
    """Default dispatcher declares the `tools` capability; Fix Day 4
    Task 2 adds `resources` via the separate register_resources path,
    so a bare build_default_dispatcher() shows tools only — the
    register_resources coverage lives in tests/test_mcp_resources.py.
    """
    d = build_default_dispatcher()
    req = JsonRpcRequest(
        method="initialize",
        params={"protocolVersion": PROTOCOL_VERSION, "capabilities": {}},
        id=1,
        is_notification=False,
    )
    resp = await d.dispatch(req)
    assert resp is not None
    assert resp["id"] == 1
    result = resp["result"]
    assert result["protocolVersion"] == PROTOCOL_VERSION
    assert result["capabilities"] == {"tools": {}}
    assert result["serverInfo"] == {"name": SERVER_NAME, "version": SERVER_VERSION}


@pytest.mark.asyncio
async def test_declare_capability_reflects_in_initialize_response():
    """An additive capability declaration made after build_default_dispatcher()
    but before the initialize call surfaces in the initialize response —
    this is the contract that register_resources relies on.
    """
    d = build_default_dispatcher()
    d.declare_capability("resources", {})
    req = JsonRpcRequest(
        method="initialize",
        params={"protocolVersion": PROTOCOL_VERSION},
        id=1,
        is_notification=False,
    )
    resp = await d.dispatch(req)
    assert resp["result"]["capabilities"] == {"tools": {}, "resources": {}}


@pytest.mark.asyncio
async def test_initialize_protocol_mismatch_logged_not_rejected(caplog):
    """Client sends a future/different protocol version. Per the
    directive: log INFO, respond with pinned version, let the
    client decide. No hostile erroring.
    """
    d = build_default_dispatcher()
    req = JsonRpcRequest(
        method="initialize",
        params={"protocolVersion": "2099-01-01"},
        id=2,
        is_notification=False,
    )
    with caplog.at_level(logging.INFO, logger="adapters.claude_code.dispatcher"):
        resp = await d.dispatch(req)
    assert resp["result"]["protocolVersion"] == PROTOCOL_VERSION
    # Mismatch logged at INFO with both sides named.
    matching = [r for r in caplog.records if "protocol_mismatch" in r.getMessage()]
    assert len(matching) == 1
    assert "2099-01-01" in matching[0].getMessage()
    assert PROTOCOL_VERSION in matching[0].getMessage()


@pytest.mark.asyncio
async def test_initialized_notification_returns_none():
    d = build_default_dispatcher()
    req = JsonRpcRequest(
        method="initialized", params=None, id=None, is_notification=True
    )
    resp = await d.dispatch(req)
    assert resp is None


@pytest.mark.asyncio
async def test_notifications_initialized_also_accepted():
    """Some MCP clients send `notifications/initialized` as the
    canonical namespaced name; we accept both.
    """
    d = build_default_dispatcher()
    req = JsonRpcRequest(
        method="notifications/initialized",
        params=None,
        id=None,
        is_notification=True,
    )
    resp = await d.dispatch(req)
    assert resp is None


@pytest.mark.asyncio
async def test_tools_list_empty_on_day_2():
    """Day 2 framework ships with no registered tools; N11 fills
    this in Day 3. Assertion pins that contract.
    """
    d = build_default_dispatcher()
    req = JsonRpcRequest(
        method="tools/list", params=None, id=3, is_notification=False
    )
    resp = await d.dispatch(req)
    assert resp["result"] == {"tools": []}


@pytest.mark.asyncio
async def test_tools_list_reflects_registered_tools():
    """After N11 registers a tool, tools/list advertises it."""
    d = build_default_dispatcher()

    async def _fake(args):
        return {"content": [{"type": "text", "text": "ok"}], "isError": False}

    d.register_tool(
        ToolSpec(
            name="concierge_recommend",
            description="Rank tools for a task.",
            input_schema={"type": "object", "properties": {"task": {"type": "string"}}},
        ),
        _fake,
    )
    req = JsonRpcRequest(
        method="tools/list", params=None, id=4, is_notification=False
    )
    resp = await d.dispatch(req)
    names = [t["name"] for t in resp["result"]["tools"]]
    assert names == ["concierge_recommend"]


@pytest.mark.asyncio
async def test_tools_call_unknown_tool_returns_ismcp_error_not_rpc_error():
    """Unknown-tool is MCP-level isError=True in the result payload,
    NOT a JSON-RPC error. The client UI surfaces these differently.
    Day 2 empty-tools means EVERY call hits this path until N11.
    """
    d = build_default_dispatcher()
    req = JsonRpcRequest(
        method="tools/call",
        params={"name": "concierge_recommend", "arguments": {"task": "x"}},
        id=5,
        is_notification=False,
    )
    resp = await d.dispatch(req)
    assert "result" in resp
    assert resp["result"]["isError"] is True
    assert "not registered" in resp["result"]["content"][0]["text"]


@pytest.mark.asyncio
async def test_tools_call_dispatches_to_registered_handler():
    d = build_default_dispatcher()

    captured: list[dict] = []

    async def _fake(args):
        captured.append(args)
        return {"content": [{"type": "text", "text": "handled"}], "isError": False}

    d.register_tool(
        ToolSpec(name="echo", description="x", input_schema={"type": "object"}),
        _fake,
    )
    req = JsonRpcRequest(
        method="tools/call",
        params={"name": "echo", "arguments": {"message": "hi"}},
        id=6,
        is_notification=False,
    )
    resp = await d.dispatch(req)
    assert resp["result"]["isError"] is False
    assert captured == [{"message": "hi"}]


@pytest.mark.asyncio
async def test_tools_call_bad_params_returns_invalid_params():
    d = build_default_dispatcher()
    req = JsonRpcRequest(
        method="tools/call",
        params="not-an-object",  # type: ignore[arg-type]
        id=7,
        is_notification=False,
    )
    resp = await d.dispatch(req)
    assert resp["error"]["code"] == INVALID_PARAMS


@pytest.mark.asyncio
async def test_tools_call_missing_name_returns_invalid_params():
    d = build_default_dispatcher()
    req = JsonRpcRequest(
        method="tools/call",
        params={"arguments": {}},
        id=8,
        is_notification=False,
    )
    resp = await d.dispatch(req)
    assert resp["error"]["code"] == INVALID_PARAMS


# ---- Generic dispatch behavior ------------------------------------------


@pytest.mark.asyncio
async def test_unknown_method_returns_method_not_found():
    d = build_default_dispatcher()
    req = JsonRpcRequest(
        method="does/not/exist", params=None, id=9, is_notification=False
    )
    resp = await d.dispatch(req)
    assert resp["error"]["code"] == METHOD_NOT_FOUND


@pytest.mark.asyncio
async def test_handler_exception_returns_internal_error(caplog):
    d = Dispatcher()

    async def _bad_handler(params):
        raise RuntimeError("simulated handler failure")

    d.register_method("boom", _bad_handler)
    req = JsonRpcRequest(
        method="boom", params=None, id=10, is_notification=False
    )
    with caplog.at_level(logging.ERROR, logger="adapters.claude_code.dispatcher"):
        resp = await d.dispatch(req)
    assert resp["error"]["code"] == INTERNAL_ERROR
    assert "RuntimeError" in resp["error"]["message"]
    # Traceback logged at ERROR so the operator can diagnose during soak.
    error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert any("handler_raised" in r.getMessage() for r in error_records)


@pytest.mark.asyncio
async def test_notification_with_raising_handler_logged_not_propagated(caplog):
    """A notification's handler error must NOT crash the dispatcher.
    Log it and continue.
    """
    d = Dispatcher()

    async def _bad(params):
        raise ValueError("nope")

    d.register_method("some/notification", _bad)
    req = JsonRpcRequest(
        method="some/notification",
        params=None,
        id=None,
        is_notification=True,
    )
    with caplog.at_level(logging.ERROR, logger="adapters.claude_code.dispatcher"):
        # Must not raise.
        resp = await d.dispatch(req)
    assert resp is None
    assert any("notification" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_unknown_notification_is_silent(caplog):
    d = build_default_dispatcher()
    req = JsonRpcRequest(
        method="unknown/notification",
        params=None,
        id=None,
        is_notification=True,
    )
    with caplog.at_level(logging.DEBUG, logger="adapters.claude_code.dispatcher"):
        resp = await d.dispatch(req)
    assert resp is None


# ---- ToolSpec -----------------------------------------------------------


class TestToolSpec:
    def test_to_mcp_shape(self):
        spec = ToolSpec(
            name="concierge_recommend",
            description="desc",
            input_schema={"type": "object"},
        )
        assert spec.to_mcp() == {
            "name": "concierge_recommend",
            "description": "desc",
            "inputSchema": {"type": "object"},
        }
