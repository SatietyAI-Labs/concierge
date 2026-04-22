"""Integration-shaped tests for `register_meta_tools(dispatcher)`.

Verifies the three N11 meta-tools land on the dispatcher with the
expected names + inputSchema shapes. These tests exercise the
registration surface the shim's `main()` uses before accepting
stdin — per N9 DECISIONS `[2026-04-22 11:48]`, meta-tools must be
registered before the first `tools/list` query arrives.
"""
from __future__ import annotations

import pytest

from adapters.claude_code.dispatcher import build_default_dispatcher
from adapters.claude_code.jsonrpc import JsonRpcRequest
from adapters.claude_code.meta_tools import register_meta_tools


def test_register_adds_all_three_meta_tools():
    dispatcher = build_default_dispatcher()
    assert dispatcher.list_tools() == []

    register_meta_tools(dispatcher)

    names = {spec["name"] for spec in dispatcher.list_tools()}
    assert names == {
        "concierge_recommend",
        "concierge_request_tool",
        "concierge_list_active",
    }


def test_registration_priority_order_recommend_first():
    """Priority order matters if a future extension throws partway
    through (Q4 revised criterion in the N11 proposal). This test
    pins the order so a refactor that changes it is caught.
    """
    dispatcher = build_default_dispatcher()
    register_meta_tools(dispatcher)

    ordered_names = [spec["name"] for spec in dispatcher.list_tools()]
    assert ordered_names[0] == "concierge_recommend"
    assert "concierge_request_tool" in ordered_names
    assert "concierge_list_active" in ordered_names


def test_each_spec_exposes_valid_inputSchema():
    dispatcher = build_default_dispatcher()
    register_meta_tools(dispatcher)

    specs = {spec["name"]: spec for spec in dispatcher.list_tools()}
    for name, spec in specs.items():
        schema = spec["inputSchema"]
        assert isinstance(schema, dict), f"{name}: inputSchema not dict"
        assert schema.get("type") == "object", f"{name}: schema type not object"
        assert "properties" in schema, f"{name}: schema missing properties"


def test_recommend_has_required_task():
    dispatcher = build_default_dispatcher()
    register_meta_tools(dispatcher)
    specs = {s["name"]: s for s in dispatcher.list_tools()}
    assert specs["concierge_recommend"]["inputSchema"]["required"] == ["task"]


def test_request_tool_has_required_tool_name():
    dispatcher = build_default_dispatcher()
    register_meta_tools(dispatcher)
    specs = {s["name"]: s for s in dispatcher.list_tools()}
    assert specs["concierge_request_tool"]["inputSchema"]["required"] == ["tool_name"]


def test_list_active_has_no_required_fields():
    dispatcher = build_default_dispatcher()
    register_meta_tools(dispatcher)
    specs = {s["name"]: s for s in dispatcher.list_tools()}
    assert specs["concierge_list_active"]["inputSchema"].get("required", []) == []


@pytest.mark.asyncio
async def test_tools_list_via_dispatcher_returns_registered():
    """End-to-end registration: after register_meta_tools, a
    `tools/list` JSON-RPC request returns the three specs in the
    response result. Mirrors what the MCP client sees over stdio.
    """
    dispatcher = build_default_dispatcher()
    register_meta_tools(dispatcher)

    request = JsonRpcRequest(
        method="tools/list", params=None, id=1, is_notification=False
    )
    response = await dispatcher.dispatch(request)

    assert response["id"] == 1
    assert "result" in response
    tools = response["result"]["tools"]
    names = {t["name"] for t in tools}
    assert "concierge_recommend" in names
    assert "concierge_request_tool" in names
    assert "concierge_list_active" in names
