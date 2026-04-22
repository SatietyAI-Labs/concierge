"""Async stdio main loop — Layer 3 of the shim architecture.

Wires stdin → parse → dispatch → serialize → stdout. Clean shutdown
on stdin EOF. Every in/out message logged at DEBUG on stderr.

Operational discipline:

- `configure_stderr_logging()` runs FIRST, before any other module
  code touches the logger. This is why import-time side effects in
  sibling modules are zero (jsonrpc.py, dispatcher.py log nothing
  at import time).
- stdout is treated as a binary channel for JSON-RPC framing. The
  only writer is `_emit()`; there are no `print()` calls anywhere
  in the package. The `test_shim_print_lint.py` test enforces this
  statically.
- stdin is read line-by-line (newline-delimited JSON, MCP's stdio
  convention). An EOF cleanly exits the loop with return code 0.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from typing import Any, Optional

from adapters.claude_code.dispatcher import Dispatcher, build_default_dispatcher
from adapters.claude_code.jsonrpc import (
    PARSE_ERROR,
    ParseError,
    make_error_response,
    parse_message,
    serialize,
)
from adapters.claude_code.logging_setup import configure_stderr_logging
from adapters.claude_code.meta_tools import register_meta_tools
from adapters.claude_code.meta_tools.http_client import aclose as _aclose_meta_tools_client


logger = logging.getLogger(__name__)


async def _stdin_lines() -> "asyncio.StreamReader":
    """Attach an asyncio StreamReader to stdin. Works on POSIX; on
    Windows, `connect_read_pipe` on stdin is not supported pre-3.12
    but this codebase targets Linux/WSL per project policy.
    """
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader(loop=loop)
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    return reader


def _emit(payload: dict[str, Any], *, out=None) -> None:
    """Write one JSON-RPC line to stdout (or `out` if injected for
    tests). Flushes so the MCP client sees the byte stream without
    buffering delay.
    """
    target = out if out is not None else sys.stdout
    line = serialize(payload)
    target.write(line)
    target.flush()


async def run(
    dispatcher: Optional[Dispatcher] = None,
    *,
    reader: Optional["asyncio.StreamReader"] = None,
    out=None,
) -> int:
    """Main event loop. Exits with 0 on stdin EOF.

    `dispatcher` / `reader` / `out` are injectable for tests; in
    production the defaults (`build_default_dispatcher`, real
    stdin/stdout) are used.
    """
    d = dispatcher if dispatcher is not None else build_default_dispatcher()
    r = reader if reader is not None else await _stdin_lines()
    logger.info("shim.startup pid=%d", _pid())
    message_count = 0
    while True:
        raw = await r.readline()
        if not raw:
            logger.info(
                "shim.shutdown reason=stdin_eof messages=%d", message_count
            )
            return 0
        message_count += 1
        text = raw.decode("utf-8", errors="replace").rstrip("\n")
        if not text.strip():
            logger.debug("shim.recv empty_line — skipped")
            continue

        start = time.monotonic()
        try:
            request = parse_message(text)
        except ParseError as exc:
            logger.warning(
                "shim.parse_error raw_len=%d error=%s", len(text), exc
            )
            _emit(
                make_error_response(None, PARSE_ERROR, str(exc)),
                out=out,
            )
            continue

        logger.debug(
            "shim.recv method=%s id=%s notification=%s",
            request.method,
            request.id,
            request.is_notification,
        )

        response = await d.dispatch(request)
        if response is not None:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.debug(
                "shim.send method=%s id=%s latency_ms=%d",
                request.method,
                request.id,
                latency_ms,
            )
            _emit(response, out=out)


def _pid() -> int:
    """Indirection so a test can monkeypatch this if needed; keeps
    the logger line stable across processes otherwise.
    """
    import os

    return os.getpid()


async def _run_with_cleanup() -> int:
    """Compose the dispatcher + register N11 meta-tools, then run the
    main loop. The `finally` block closes the shared meta-tools httpx
    AsyncClient so shutdown under SIGTERM or abrupt exit does not
    leak a "AsyncClient used without explicit close" warning into
    the soak-phase log stream.
    """
    dispatcher = build_default_dispatcher()
    register_meta_tools(dispatcher)
    try:
        return await run(dispatcher=dispatcher)
    finally:
        await _aclose_meta_tools_client()


def main() -> int:
    """CLI entrypoint. `scripts/concierge-shim` calls this.

    Configures logging first (stderr-only, never stdout), composes
    the dispatcher with N11 meta-tools, then hands off to the async
    loop. Meta-tools are registered BEFORE the stdin-read loop
    starts — per the N9 DECISIONS entry `[2026-04-22 11:48]`, the
    client's startup `tools/list` query arrives within milliseconds
    of `notifications/initialized`, so meta-tools must be on the
    dispatcher before that point.
    """
    configure_stderr_logging(level="DEBUG")
    try:
        return asyncio.run(_run_with_cleanup())
    except KeyboardInterrupt:
        logger.info("shim.shutdown reason=keyboard_interrupt")
        return 130


if __name__ == "__main__":
    sys.exit(main())
