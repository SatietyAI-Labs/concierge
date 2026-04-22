#!/usr/bin/env python3
"""Mock MCP backing server for N13 integration tests.

Reads JSON-RPC lines from stdin, emits canned responses on stdout.
Behavior-gated via env vars so each test exercises a specific path
without needing separate fixture files:

    MOCK_MCP_TOOL_PREFIX          Prefix for advertised tools (default "mock_")
    MOCK_MCP_FAIL_INITIALIZE      If "1", respond to initialize with error
    MOCK_MCP_DELAY_INIT_SECONDS   Float; sleep before initialize response
    MOCK_MCP_CRASH_BEFORE_INIT    If "1", exit immediately (no stdin read)
    MOCK_MCP_TOOL_BEHAVIOR        "success" (default) | "error" | "slow"

Stdout-purity invariant: every line to stdout is valid JSON-RPC.
Stderr used for any diagnostic logging (test harness ignores).

NOT a Concierge-production module — throwaway test helper.
"""
import json
import os
import sys
import time


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _envflag(name: str) -> bool:
    return os.environ.get(name, "") == "1"


def _emit(msg: dict) -> None:
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def _tool_inventory(prefix: str) -> list[dict]:
    return [
        {
            "name": f"{prefix}ping",
            "description": "Mock backing-server ping tool.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": f"{prefix}echo",
            "description": "Echo back the arguments object.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                },
            },
        },
    ]


def _handle_initialize(msg_id, prefix: str) -> None:
    delay = _env("MOCK_MCP_DELAY_INIT_SECONDS", "0")
    try:
        delay_s = float(delay)
    except ValueError:
        delay_s = 0.0
    if delay_s > 0:
        time.sleep(delay_s)

    if _envflag("MOCK_MCP_FAIL_INITIALIZE"):
        _emit(
            {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32000,
                    "message": "mock fixture: initialize forced to fail",
                },
            }
        )
        return

    _emit(
        {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2025-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "mock-mcp-backing", "version": "0.0.1"},
            },
        }
    )


def _handle_tools_call(msg_id, params: dict, prefix: str) -> None:
    behavior = _env("MOCK_MCP_TOOL_BEHAVIOR", "success")
    tool_name = params.get("name", "")
    args = params.get("arguments", {}) or {}

    if behavior == "slow":
        # Longer than the tool-call timeout (30s); test overrides the
        # timeout to a smaller value via monkeypatch if exercising this.
        time.sleep(35)

    if behavior == "error":
        _emit(
            {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32000,
                    "message": f"mock fixture: tool {tool_name!r} forced to error",
                },
            }
        )
        return

    # Success path: echo a content block referencing tool_name + args
    _emit(
        {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": f"mock-{tool_name} called with {json.dumps(args)}",
                    }
                ],
                "isError": False,
            },
        }
    )


def main() -> int:
    if _envflag("MOCK_MCP_CRASH_BEFORE_INIT"):
        return 1

    prefix = _env("MOCK_MCP_TOOL_PREFIX", "mock_")

    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue

        method = msg.get("method")
        msg_id = msg.get("id")

        if method == "initialize":
            _handle_initialize(msg_id, prefix)
        elif method == "notifications/initialized":
            # Notification; no response. Mock server is now "ready".
            pass
        elif method == "tools/list":
            _emit(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"tools": _tool_inventory(prefix)},
                }
            )
        elif method == "tools/call":
            _handle_tools_call(msg_id, msg.get("params", {}) or {}, prefix)
        elif msg_id is not None:
            # Unknown method with an id → error response
            _emit(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32601,
                        "message": f"mock fixture: method {method!r} not implemented",
                    },
                }
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
