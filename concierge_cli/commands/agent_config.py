"""`concierge enable` / `concierge disable` subcommands — Stage 1A item 1b.

Both mutate one `mcp.servers` entry in an agent's `openclaw.json`:

- ``concierge enable <agent> <server> --config-file P``  — insert/replace
- ``concierge enable <agent> <server> --config-json '{...}'``
- ``concierge disable <agent> <server>``                 — remove

Architecture — direct in-process call, NOT an HTTP shim
-------------------------------------------------------
`recommend` / `request-tool` / `list-active` are HTTP shims because
their work lives in the Concierge service (LLM, database). `enable` /
`disable` are the principled outliers: they call
`core.agent_config.openclaw_writer.set_mcp_server` directly, in
process. The rationale (locked as item-1b Decision D1, logged at close
per the D47 placement-deviation precedent):

- Zero server-side state — no DB write, no LLM, no async work, no SSE.
- The writer is library-shaped (typed exceptions, atomic `.bak` +
  `os.replace`); importing and calling it is the honest shape.
- Config mutation must work whether the Concierge service is up or
  down. Routing a local-filesystem write through the running daemon
  would couple openclaw.json mutation to daemon liveness — the wrong
  dependency for a local-fs mutator.

This is a deliberate deviation from master plan v1.1 §III.2's implicit
"each subcommand makes one HTTP call" pattern.

Error contract
--------------
Every client-side / local-filesystem failure maps to `UsageError`
(exit 2): unknown agent codename, malformed `--config-json`, missing
`--config-file`, a non-object config payload, an openclaw.json that is
absent or corrupt on disk. Exit 2 means "fix something locally and
retry" — distinct from the HTTP taxonomy (3/4/5/6), which `enable` /
`disable` never reach because they make no HTTP call. No new exit code
is introduced (consistent with item-1b Decision D7).

Live-path safety
----------------
There is deliberately NO operator-facing ``--config-path`` flag
(item-1b Decision D6): the live target resolves from the writer's
`AGENT_PATHS` and is unforgeable from the CLI surface. Tests exercise
non-live paths by patching `AGENT_PATHS` (real writer, `tmp_path`
target) or by mocking `set_mcp_server` at this module's import
boundary.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from concierge_cli.errors import UsageError
from concierge_cli.output import render_agent_config
from core.agent_config.openclaw_writer import (
    AGENT_PATHS,
    UnknownAgentError,
    set_mcp_server,
)


def _add_target_args(sub: argparse.ArgumentParser) -> None:
    """The agent + server positionals are shared by enable and disable."""
    sub.add_argument(
        "agent_id",
        metavar="AGENT",
        help=(
            "Agent codename: one of alfred, scout, dispatch, radar, "
            "bridge."
        ),
    )
    sub.add_argument(
        "server_name",
        metavar="SERVER",
        help=(
            "Name of the MCP server entry under `mcp.servers` "
            "(e.g. 'memory', 'firefox')."
        ),
    )


def register_enable(subparsers: argparse._SubParsersAction) -> None:
    sub = subparsers.add_parser(
        "enable",
        help=(
            "Enable (insert or replace) an MCP server entry in an "
            "agent's openclaw.json config."
        ),
    )
    _add_target_args(sub)
    # Exactly one config source is required. Mutually-exclusive group
    # with required=True enforces both halves of D2 at the argparse
    # layer: passing both flags or neither exits 2 before run() is
    # reached. Mirrors `git commit -m` vs `git commit -F`.
    config_source = sub.add_mutually_exclusive_group(required=True)
    config_source.add_argument(
        "--config-file",
        dest="config_file",
        default=None,
        help=(
            "Path to a JSON file holding the server config object to "
            "install at mcp.servers[SERVER]. Mutually exclusive with "
            "--config-json."
        ),
    )
    config_source.add_argument(
        "--config-json",
        dest="config_json",
        default=None,
        help=(
            "Inline JSON object string for the server config "
            "(e.g. '{\"command\": \"npx\", \"args\": [\"-y\", \"pkg\"]}'). "
            "Mutually exclusive with --config-file."
        ),
    )
    sub.add_argument(
        "--json",
        action="store_true",
        dest="emit_json",
        help="Emit a JSON result object to stdout instead of rendered text.",
    )
    sub.set_defaults(func=run_enable)


def register_disable(subparsers: argparse._SubParsersAction) -> None:
    sub = subparsers.add_parser(
        "disable",
        help=(
            "Disable (remove) an MCP server entry from an agent's "
            "openclaw.json config. Idempotent — removing an "
            "already-absent server succeeds with no change."
        ),
    )
    _add_target_args(sub)
    sub.add_argument(
        "--json",
        action="store_true",
        dest="emit_json",
        help="Emit a JSON result object to stdout instead of rendered text.",
    )
    sub.set_defaults(func=run_disable)


def _resolve_agent_id(raw: str) -> str:
    """Validate `raw` against the writer's AGENT_PATHS codename set.

    Pre-validating here (rather than letting `set_mcp_server` raise
    `UnknownAgentError`) lets the CLI surface a codename typo before
    any config parsing, with a CLI-framed exit-2 message.
    """
    if raw not in AGENT_PATHS:
        raise UsageError(
            f"unknown agent codename {raw!r} — "
            f"expected one of {sorted(AGENT_PATHS)}"
        )
    return raw


def _load_config(args: argparse.Namespace) -> dict[str, Any]:
    """Read + parse the server config from --config-file or --config-json.

    The mutually-exclusive-required group guarantees exactly one is
    set, so the else-branch covers --config-json. Any parse / read /
    shape failure raises `UsageError` (exit 2).
    """
    if args.config_file is not None:
        path = Path(args.config_file)
        if not path.exists():
            raise UsageError(f"--config-file not found: {path}")
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise UsageError(f"could not read --config-file {path}: {exc}")
        source = f"--config-file {path}"
    else:
        raw = args.config_json
        source = "--config-json"

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UsageError(f"{source} is not valid JSON: {exc}")

    if not isinstance(parsed, dict):
        raise UsageError(
            f"{source} must be a JSON object (the mcp.servers entry "
            f"config); got {type(parsed).__name__}"
        )
    return parsed


def _emit(args: argparse.Namespace, action: str, agent_id: str, server: str) -> None:
    """Render the confirmation, honoring --json."""
    if args.emit_json:
        print(
            json.dumps(
                {
                    "action": action,
                    "agent_id": agent_id,
                    "server_name": server,
                    "status": "ok",
                }
            )
        )
    else:
        render_agent_config(action, agent_id, server, sys.stdout)


def _call_writer(
    agent_id: str, server_name: str, server_config: Optional[dict[str, Any]]
) -> None:
    """Invoke `set_mcp_server`, mapping its operational exceptions onto
    `UsageError` (exit 2). `UnknownAgentError` is normally pre-empted
    by `_resolve_agent_id`; it is caught here too as defense in depth.
    """
    try:
        set_mcp_server(agent_id, server_name, server_config)
    except UnknownAgentError as exc:
        raise UsageError(str(exc))
    except FileNotFoundError as exc:
        raise UsageError(str(exc))
    except json.JSONDecodeError as exc:
        # The writer re-raises with the offending file path in the
        # message — surface that verbatim to the operator.
        raise UsageError(f"openclaw.json is not valid JSON: {exc}")


def run_enable(args: argparse.Namespace) -> int:
    agent_id = _resolve_agent_id(args.agent_id)
    server_config = _load_config(args)
    _call_writer(agent_id, args.server_name, server_config)
    _emit(args, "enable", agent_id, args.server_name)
    return 0


def run_disable(args: argparse.Namespace) -> int:
    agent_id = _resolve_agent_id(args.agent_id)
    _call_writer(agent_id, args.server_name, None)
    _emit(args, "disable", agent_id, args.server_name)
    return 0
