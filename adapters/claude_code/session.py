"""Shim-lifetime session identifier for telemetry correlation.

Fix Day 4 Task 6 — session_id propagation. The shim generates one
UUID4 per process at import time and exports it as
`SHIM_SESSION_ID`. Meta-tool handlers include this value in every
HTTP request body that carries a session_id field (currently
`/recommend`; future: MCP-originated `/requests/{filename}/status`
approvals).

## Lifetime semantics

One shim process = one session_id. The value does NOT persist
across restarts — each time `concierge-shim` starts fresh, a new
UUID4 is minted. This matches operator intuition: a "session" is
one continuous MCP connection, ended when the shim process exits
(stdin EOF, SIGTERM, or Claude Code disconnecting).

Long-running shim processes accumulate events under a single
session_id; short-lived ones produce more distinct ids. Both are
valid scanner signals — the scanner queries by tool + window, not
by session directly.

## Why module-level

UUID4 generation is pure and cheap (~microseconds). Generating at
import time means every handler importer sees the same value
without needing to pass it via DI. An alternative would be a
contextvar, but the shim is single-process single-event-loop so
the simpler shape is correct here.

## Testability

Tests that need a deterministic session_id can monkeypatch this
module's attribute:

    monkeypatch.setattr(
        "adapters.claude_code.session.SHIM_SESSION_ID",
        "test-session-fixed-uuid",
    )

The meta-tool handlers read `session.SHIM_SESSION_ID` at call time
(not captured at import), so monkeypatched values take effect
immediately.
"""
from __future__ import annotations

import uuid


SHIM_SESSION_ID: str = str(uuid.uuid4())
"""UUID4 minted at module import. One per shim process.

MCP-originated calls include this in telemetry-capable HTTP bodies
so `ToolUsageEvent` rows carry a consistent correlation id across
the session. Non-MCP callers (the FastAPI service's own direct use,
the UI) leave session_id null and do not read this constant.
"""


__all__ = ["SHIM_SESSION_ID"]
