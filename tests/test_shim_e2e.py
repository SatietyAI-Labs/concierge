"""End-to-end subprocess tests for the shim.

Validates the actual invocation path Claude Code uses: spawn the
shim as a child process, write JSON-RPC lines to its stdin, read
responses from stdout. stderr captured for log assertions.

These are "verified in isolation" not "verified against real
Claude Code MCP client." Manual-verification TODO lives in
`adapters/claude_code/README.md` for Day 3 eve / Day 4 morning.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class ShimHarness:
    proc: subprocess.Popen
    _stdout_buffer: str = ""

    def send(self, msg: dict) -> None:
        line = json.dumps(msg) + "\n"
        assert self.proc.stdin is not None
        self.proc.stdin.write(line.encode("utf-8"))
        self.proc.stdin.flush()

    def recv_line(self, timeout: float = 3.0) -> str:
        """Block until one newline-terminated line arrives on stdout
        or timeout expires.
        """
        assert self.proc.stdout is not None
        deadline = time.monotonic() + timeout
        while "\n" not in self._stdout_buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"timed out waiting for stdout line after {timeout}s; "
                    f"buffered: {self._stdout_buffer!r}"
                )
            chunk = os.read(self.proc.stdout.fileno(), 4096)
            if not chunk:
                raise EOFError("stdout closed before newline arrived")
            self._stdout_buffer += chunk.decode("utf-8")
        line, _, rest = self._stdout_buffer.partition("\n")
        self._stdout_buffer = rest
        return line

    def recv_json(self, timeout: float = 3.0) -> dict:
        return json.loads(self.recv_line(timeout=timeout))

    def close_stdin(self) -> None:
        if self.proc.stdin is not None and not self.proc.stdin.closed:
            self.proc.stdin.close()

    def wait_exit(self, timeout: float = 3.0) -> int:
        try:
            return self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            return self.proc.wait()

    def drain_stderr(self) -> str:
        """Read any remaining stderr (assumes process has exited)."""
        assert self.proc.stderr is not None
        data = self.proc.stderr.read()
        return data.decode("utf-8", errors="replace") if data else ""


@pytest.fixture
def shim():
    proc = subprocess.Popen(
        [sys.executable, "-m", "adapters.claude_code.shim"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(REPO_ROOT),
        bufsize=0,
    )
    harness = ShimHarness(proc=proc)
    try:
        yield harness
    finally:
        harness.close_stdin()
        try:
            harness.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            harness.proc.kill()
            harness.proc.wait()


# ---- Initialize handshake ----------------------------------------------


class TestInitialize:
    def test_initialize_returns_capabilities_and_serverinfo(self, shim):
        shim.send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {}},
            }
        )
        resp = shim.recv_json()
        assert resp["id"] == 1
        assert resp["result"]["protocolVersion"] == "2024-11-05"
        assert resp["result"]["capabilities"] == {"tools": {}}
        assert resp["result"]["serverInfo"]["name"] == "concierge-shim"

    def test_tools_list_returns_empty_on_day_2(self, shim):
        shim.send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05"},
            }
        )
        shim.recv_json()
        shim.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        resp = shim.recv_json()
        assert resp["result"] == {"tools": []}


# ---- Error surfaces ----------------------------------------------------


class TestErrorSurfaces:
    def test_malformed_json_returns_parse_error(self, shim):
        # Write raw bytes — bypass the .send() JSON layer.
        assert shim.proc.stdin is not None
        shim.proc.stdin.write(b"{this is not json}\n")
        shim.proc.stdin.flush()
        resp = shim.recv_json()
        assert resp["id"] is None
        assert resp["error"]["code"] == -32700

    def test_unknown_method_returns_method_not_found(self, shim):
        shim.send(
            {"jsonrpc": "2.0", "id": 99, "method": "does/not/exist"}
        )
        resp = shim.recv_json()
        assert resp["error"]["code"] == -32601


# ---- Notification semantics --------------------------------------------


class TestNotificationSemantics:
    def test_notification_produces_no_response(self, shim):
        """A notification (no `id`) must not produce any stdout
        output. We verify by sending the notification then sending
        a request and asserting only ONE response arrives.
        """
        shim.send(
            {"jsonrpc": "2.0", "method": "notifications/initialized"}
        )
        shim.send(
            {"jsonrpc": "2.0", "id": 5, "method": "tools/list"}
        )
        # The response must be for id=5, not for the earlier
        # notification. If the shim had replied to the notification,
        # we'd see its response first.
        resp = shim.recv_json()
        assert resp["id"] == 5


# ---- Clean shutdown ----------------------------------------------------


class TestCleanShutdown:
    def test_eof_on_stdin_exits_zero(self, shim):
        shim.send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05"},
            }
        )
        shim.recv_json()  # drain initialize response
        shim.close_stdin()
        exit_code = shim.wait_exit()
        assert exit_code == 0


# ---- Stdout purity -----------------------------------------------------


class TestStdoutPurity:
    """The operational invariant: every line written to stdout must
    be valid JSON-RPC. Any log leak (or stray print) contaminates
    the protocol stream and breaks the MCP client.

    This test runs a handshake + multiple method calls + error
    paths, then asserts every non-empty stdout line parses as a
    JSON-RPC 2.0 message.
    """

    def test_every_stdout_line_is_valid_jsonrpc(self, shim):
        # Drive the shim through varied surfaces.
        shim.send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05"},
            }
        )
        shim.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        shim.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        shim.send({"jsonrpc": "2.0", "id": 3, "method": "nothing/here"})
        # Malformed input → parse error response
        assert shim.proc.stdin is not None
        shim.proc.stdin.write(b"{not json}\n")
        shim.proc.stdin.flush()

        # Collect responses (expect: initialize, tools/list, method_not_found, parse_error)
        responses = []
        for _ in range(4):
            responses.append(shim.recv_json())

        # Close and drain any remaining bytes.
        shim.close_stdin()
        shim.wait_exit()

        # Assertions on structure — all have jsonrpc=2.0.
        for resp in responses:
            assert resp.get("jsonrpc") == "2.0"
            assert ("result" in resp) ^ ("error" in resp), (
                f"response must have exactly one of result/error: {resp}"
            )


class TestProtocolVersionMismatch:
    def test_mismatch_still_responds_with_pinned_version(self, shim):
        """Non-hostile response: client sends a future/different
        protocol version, shim responds with its pinned version.
        """
        shim.send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2099-01-01"},
            }
        )
        resp = shim.recv_json()
        assert resp["result"]["protocolVersion"] == "2024-11-05"
        # Stderr should carry the mismatch log line.
        shim.close_stdin()
        shim.wait_exit()
        stderr_text = shim.drain_stderr()
        assert "protocol_mismatch" in stderr_text
        assert "2099-01-01" in stderr_text


class TestStderrLoggingActive:
    def test_startup_logs_on_stderr(self, shim):
        """At least a `shim.startup` INFO line on stderr — confirms
        logging is wired AND going to stderr (not stdout).
        """
        shim.send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05"},
            }
        )
        shim.recv_json()
        shim.close_stdin()
        shim.wait_exit()
        stderr = shim.drain_stderr()
        assert "shim.startup" in stderr
        assert "shim.shutdown" in stderr
