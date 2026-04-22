# Claude Code adapter

Package-friendly path (`claude_code`, underscore) chosen over the
hyphenated `claude-code` so `import adapters.claude_code.shim` is
a valid Python import. The filesystem rename was done via `git mv`
so history follows.

## Current state

N10 **framework only** — Day 2 evening. Meta-tool handlers, backing-
server forwarding, and gap-report augmentation all land Day 3 per
the scope split logged at DECISIONS [2026-04-22 build N10 start].

Four layers, each separately tested:

1. `jsonrpc.py` — parse/serialize JSON-RPC 2.0 (pure functions)
2. `dispatcher.py` — async method registry; built-in `initialize`,
   `initialized`, `tools/list`, `tools/call` handlers
3. `shim.py` — asyncio stdin→parse→dispatch→serialize→stdout pump
4. `logging_setup.py` — stderr-only logger (stdout is JSON-RPC only)

Build items queued:

- **N11** (Day 3 morning) — meta-tool handlers
  (`concierge_recommend`, `concierge_request_tool`,
  `concierge_list_active`). Register onto the existing dispatcher;
  fill in `tools/list` content + `tools/call` dispatch.
- **N12** (Day 3 midday) — gap-report injection. Augments the
  `concierge_recommend` result payload.
- **N13** (Day 3 afternoon) — backing-server spawn/teardown
  lifecycle.  Adds `backing_server.py` and prefix-based routing to
  the dispatcher.
- **N14** (Day 3 afternoon) — end-to-end integration smoke.

## Entrypoint

```
scripts/concierge-shim
```

Wrapper script that execs `python3 -m adapters.claude_code.shim`.
Claude Code MCP config points at this wrapper path.

## Environment

- `CONCIERGE_URL` (default `http://127.0.0.1:8000`) — Concierge HTTP
  service URL the shim will reach when meta-tool handlers (N11)
  are wired up. Day 2 framework does not touch this; HTTP client
  construction is deferred to N11's handler registration.
- All logging goes to stderr. **Never** print to stdout — stdout is
  reserved for JSON-RPC framing and a single contaminating byte
  kills the Claude Code MCP client. The print-lint test
  (`tests/test_shim_print_lint.py`) enforces this invariant at the
  package level.

## Manual-verification TODO (Day 3 eve / Day 4 morning)

**Not Day 2 tonight's problem.** Day 2 framework is verified in
isolation via the subprocess harness (`tests/test_shim_e2e.py`) —
that's correct, but it's "verified in isolation," not "verified
against real Claude Code MCP client." Before soak begins:

1. Wire the shim into Claude Code's MCP config (a local
   `.mcp.json` referencing `scripts/concierge-shim`).
2. Launch a Claude Code session; confirm the `initialize` handshake
   completes (no stderr gibberish, no hang).
3. Confirm `tools/list` surfaces the N11 meta-tools once they land.
4. Invoke `concierge_recommend` from within the Claude Code session
   with the canonical `planning/test-fixtures/sample-task.md`; confirm
   a ranked response makes it back through the JSON-RPC round-trip.
5. Log any protocol-version mismatch observed (we pin
   `2024-11-05`; MCP client may have moved).

Until that manual-verification pass happens, "the shim works" =
"the subprocess harness says it works." Don't conflate.

## References

See `planning/build-plan.md` §F.2.2 and §F.2.3 for the full N10/
N11/N12/N13/N14 dependency chain and Day-2-vs-Day-3 scope
boundaries.
