"""N13 — backing-server subprocess lifecycle + JSON-RPC proxy.

A **backing server** is a separate MCP server subprocess that Concierge
spawns on behalf of Claude Code. Claude Code talks only to Concierge
(Approach 2 committed per DECISIONS `[2026-04-22 11:48]`); Concierge
multiplexes over its own meta-tools + prefix-routed backing-server
tools. Example: a `firefox_` prefix routes `firefox_navigate_page`
to the firefox backing server via stdio JSON-RPC.

## Lifecycle decisions (per N13 proposal Q1-Q3)

- **Spawn timing: lazy on first tool-call** (Q1a). A Claude Code
  session that never invokes a backing-server tool pays no cost.
  Initialize latency of the shim is decoupled from backing-server
  readiness — shim still responds to MCP initialize sub-second
  regardless of backing-server inventory.
- **Readiness: synchronous at spawn time** (Q2). `start()` awaits
  the full MCP initialize handshake (including tools/list fetch)
  before returning; concurrent call_tool invocations await the
  in-flight initialization via an asyncio.Event.
- **Shutdown ownership: shim-owned** (Q3). The shim's `main()` finally
  block calls `registry.shutdown_all()` which awaits each backing
  server's `stop()`. Graceful stdin-close → 3s wait → SIGTERM → 2s
  → SIGKILL cascade.

## Tool-inventory declaration

`BackingServerSpec.tool_inventory` is a **mandatory pre-declared list**
of the tools the backing server exposes. This preserves lazy-spawn
while letting `tools/list` responses to Claude Code include the full
backing-server surface from the first call (without needing to
spawn every backing server at shim startup).

Auto-discovery (fetch tools/list from the backing server at
registration time or first use) is deferred to Phase 2. For V1,
the operator registering a backing server is responsible for
pre-declaring its inventory; drift between spec and reality is
observable in soak via failed tool-calls with "method not found"
errors from the backing server.

## Out of V1 scope

- Retry-with-backoff on spawn failure (one attempt per session)
- Restart API for failed backing servers
- Config-file-driven registration (programmatic only)
- Orphan handling under parent SIGKILL (`os.setsid()` / process-group
  cleanup). Accepted risk per Q3 — soak will surface if it matters.
- Tool-inventory refresh mid-session (backing server's
  tools/list_changed notifications are ignored in V1)
- Streaming / chunked tool responses
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional


logger = logging.getLogger(__name__)


INITIALIZE_TIMEOUT_SECONDS = 5.0
TOOL_CALL_TIMEOUT_SECONDS = 30.0
GRACEFUL_STOP_TIMEOUT_SECONDS = 3.0
TERMINATE_TIMEOUT_SECONDS = 2.0
PROTOCOL_VERSION = "2025-11-05"
CLIENT_NAME = "concierge-shim"
CLIENT_VERSION = "0.1.0"


class BackingServerNotReadyError(RuntimeError):
    """Raised (internally) when a tool-call targets a BackingServer
    that failed to initialize or has crashed. Callers at the MCP
    surface convert this to an `isError=True` tools/call result
    rather than propagating — the shim must never crash on a
    backing-server failure.
    """


class PrefixCollisionError(ValueError):
    """Raised when two BackingServerSpecs register with the same
    `tool_prefix`. Prefix is the routing key; silent overwrite
    would create a "which backing server serves this tool?"
    ambiguity at runtime. Fail loud at registration time.
    """


@dataclass(frozen=True)
class BackingToolSpec:
    """One tool advertised by a backing server. Shape mirrors the
    MCP tools/list entry + the adapter's own `ToolSpec`. Kept
    separate from `adapters.claude_code.dispatcher.ToolSpec` to
    avoid coupling the generic dispatcher surface to backing-server
    specifics.
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


@dataclass(frozen=True)
class BackingServerSpec:
    """Configuration for one backing MCP server.

    `name`           human-readable identifier; used in logs
    `tool_prefix`    routing key — MCP tool-calls whose name
                     starts with this prefix are forwarded to this
                     backing server. Prefix must be non-empty and
                     uniquely owned (PrefixCollisionError on
                     registration duplicate).
    `command`        argv for asyncio.create_subprocess_exec
    `tool_inventory` pre-declared list of tools the backing server
                     exposes. Mandatory; preserves lazy-spawn
                     while populating tools/list without needing
                     to spawn the backing server. Each tool's
                     `name` must start with `tool_prefix`.
    `env`            optional env-var override for the subprocess
    """

    name: str
    tool_prefix: str
    command: list[str]
    tool_inventory: list[BackingToolSpec]
    env: Optional[dict[str, str]] = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("BackingServerSpec.name must be non-empty")
        if not self.tool_prefix.strip():
            raise ValueError("BackingServerSpec.tool_prefix must be non-empty")
        if not self.command:
            raise ValueError("BackingServerSpec.command must be non-empty")
        # Validate each tool starts with the prefix — prevents
        # registering a backing server whose tools silently miss
        # the routing path.
        for t in self.tool_inventory:
            if not t.name.startswith(self.tool_prefix):
                raise ValueError(
                    f"BackingServerSpec({self.name}): tool {t.name!r} does "
                    f"not start with tool_prefix {self.tool_prefix!r}"
                )


class BackingServer:
    """Subprocess-backed MCP client. One instance per registered
    BackingServerSpec. Not thread-safe; owned by a single event loop.
    """

    def __init__(self, spec: BackingServerSpec) -> None:
        self.spec = spec
        self.proc: Optional[asyncio.subprocess.Process] = None
        self.is_ready: bool = False
        self.spawn_attempted: bool = False
        self.last_error: Optional[str] = None

        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._next_id: int = 0
        self._response_reader_task: Optional[asyncio.Task[None]] = None
        self._stopped: bool = False
        self._start_lock: asyncio.Lock = asyncio.Lock()

    # ---- Public API --------------------------------------------------

    async def ensure_started(self) -> None:
        """Lazy-spawn entry point. If already started (or attempted),
        returns immediately. Concurrent callers serialize on a lock;
        only one spawn attempt per BackingServer instance per session.
        """
        async with self._start_lock:
            if self.spawn_attempted:
                return
            self.spawn_attempted = True
            try:
                await self._start()
            except Exception as exc:
                self.is_ready = False
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "backing_server.start_failed name=%s error=%s",
                    self.spec.name,
                    self.last_error,
                )

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Forward a tools/call to the backing server. Returns the
        MCP-shaped result dict (with isError flag). Callers that
        receive BackingServerNotReadyError should wrap in the
        isError=True envelope at the meta-tool surface.
        """
        await self.ensure_started()
        if not self.is_ready or self.proc is None:
            raise BackingServerNotReadyError(
                f"backing server {self.spec.name!r} is not ready: "
                f"{self.last_error or 'no diagnostic available'}"
            )

        call_id = self._allocate_id()
        future = self._register_pending(call_id)
        await self._write_line(
            {
                "jsonrpc": "2.0",
                "id": call_id,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            }
        )
        try:
            response = await asyncio.wait_for(
                future, timeout=TOOL_CALL_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            self._pending.pop(call_id, None)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Backing server {self.spec.name!r} timed out "
                            f"after {TOOL_CALL_TIMEOUT_SECONDS:.0f}s."
                        ),
                    }
                ],
                "isError": True,
            }

        if "error" in response:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Backing server {self.spec.name!r} returned an "
                            f"error: {response['error'].get('message', 'unknown')}"
                        ),
                    }
                ],
                "isError": True,
            }
        result = response.get("result", {}) or {}
        return result

    async def stop(self) -> None:
        """Graceful teardown: stdin-close → wait → SIGTERM → wait →
        SIGKILL cascade. Safe to call multiple times; safe to call
        before start() (no-op).
        """
        if self._stopped or self.proc is None:
            return
        self._stopped = True
        self.is_ready = False

        # Close stdin to signal clean shutdown to the backing server.
        if self.proc.stdin is not None:
            try:
                self.proc.stdin.close()
            except Exception:  # defensive — closing may race with process exit
                pass

        # Try graceful exit
        try:
            await asyncio.wait_for(
                self.proc.wait(), timeout=GRACEFUL_STOP_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            logger.info(
                "backing_server.graceful_timeout name=%s — sending SIGTERM",
                self.spec.name,
            )
            try:
                self.proc.terminate()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(
                    self.proc.wait(), timeout=TERMINATE_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "backing_server.terminate_timeout name=%s — SIGKILL",
                    self.spec.name,
                )
                try:
                    self.proc.kill()
                except ProcessLookupError:
                    pass
                await self.proc.wait()

        # Cancel the response reader if still running
        if self._response_reader_task and not self._response_reader_task.done():
            self._response_reader_task.cancel()
            try:
                await self._response_reader_task
            except (asyncio.CancelledError, Exception):
                pass

    # ---- Private: spawn + handshake ---------------------------------

    async def _start(self) -> None:
        logger.info(
            "backing_server.spawn name=%s prefix=%s command=%s",
            self.spec.name,
            self.spec.tool_prefix,
            " ".join(self.spec.command),
        )
        try:
            self.proc = await asyncio.create_subprocess_exec(
                *self.spec.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self.spec.env,
            )
        except (FileNotFoundError, OSError) as exc:
            raise RuntimeError(f"spawn failed: {exc}") from exc

        # Start reading responses before sending initialize, so the
        # initialize response doesn't race with the reader-task boot.
        self._response_reader_task = asyncio.create_task(self._response_reader())

        # MCP initialize handshake
        init_id = self._allocate_id()
        init_future = self._register_pending(init_id)
        await self._write_line(
            {
                "jsonrpc": "2.0",
                "id": init_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {
                        "name": CLIENT_NAME,
                        "version": CLIENT_VERSION,
                    },
                },
            }
        )
        try:
            init_response = await asyncio.wait_for(
                init_future, timeout=INITIALIZE_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            self._pending.pop(init_id, None)
            raise RuntimeError(
                f"initialize timeout after {INITIALIZE_TIMEOUT_SECONDS:.0f}s"
            )

        if "error" in init_response:
            raise RuntimeError(
                f"initialize returned error: "
                f"{init_response['error'].get('message', 'unknown')}"
            )

        # Send the post-initialize notification
        await self._write_line(
            {"jsonrpc": "2.0", "method": "notifications/initialized"}
        )

        # Backing server's tool inventory is pre-declared on the spec;
        # we don't fetch tools/list here (V1 contract — see module
        # docstring). The backing server is now ready.
        self.is_ready = True
        logger.info(
            "backing_server.ready name=%s tools_declared=%d",
            self.spec.name,
            len(self.spec.tool_inventory),
        )

    # ---- Private: response reader + id plumbing ---------------------

    async def _response_reader(self) -> None:
        """Consume stdout lines, parse JSON-RPC, dispatch to pending
        Futures by id. Exits on stdin EOF (backing server exit).
        """
        assert self.proc is not None
        assert self.proc.stdout is not None
        try:
            while True:
                line = await self.proc.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip("\n")
                if not text.strip():
                    continue
                try:
                    msg = json.loads(text)
                except json.JSONDecodeError as exc:
                    logger.warning(
                        "backing_server.bad_json name=%s line=%r error=%s",
                        self.spec.name,
                        text[:200],
                        exc,
                    )
                    continue
                msg_id = msg.get("id")
                if isinstance(msg_id, int) and msg_id in self._pending:
                    fut = self._pending.pop(msg_id)
                    if not fut.done():
                        fut.set_result(msg)
                else:
                    # Notifications from the backing server (e.g.
                    # tools/list_changed) are ignored in V1.
                    logger.debug(
                        "backing_server.unmatched name=%s method=%s id=%r",
                        self.spec.name,
                        msg.get("method"),
                        msg_id,
                    )
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.warning(
                "backing_server.reader_error name=%s error=%s",
                self.spec.name,
                exc,
            )
            # Fail any pending futures so callers don't hang.
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(
                        BackingServerNotReadyError(
                            f"backing server {self.spec.name!r} reader crashed: {exc}"
                        )
                    )
            self._pending.clear()
            self.is_ready = False

    async def _write_line(self, msg: dict[str, Any]) -> None:
        assert self.proc is not None
        assert self.proc.stdin is not None
        line = (json.dumps(msg) + "\n").encode("utf-8")
        self.proc.stdin.write(line)
        await self.proc.stdin.drain()

    def _allocate_id(self) -> int:
        self._next_id += 1
        return self._next_id

    def _register_pending(self, msg_id: int) -> asyncio.Future[dict[str, Any]]:
        loop = asyncio.get_event_loop()
        fut: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[msg_id] = fut
        return fut
