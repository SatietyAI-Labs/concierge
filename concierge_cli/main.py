"""argparse dispatch for the `concierge` CLI.

Two-layer error contract:
1. `client.py` maps specific httpx failure modes to typed
   `ConciergeCliError` subclasses (exits 3 / 4 / 5 / 6).
2. The outer `httpx.TransportError` catch-all here is the second
   layer — anything httpx-level that slips past client.py's
   specific handling (e.g., `PoolTimeout`, `RemoteProtocolError`,
   `WriteError`) routes to exit 3 with the same
   service-unreachable user message. The catch-all is REQUIRED,
   not optional; do not remove without re-thinking the contract.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Optional, Sequence

import httpx

from concierge_cli import __version__
from concierge_cli.client import DEFAULT_BASE_URL
from concierge_cli.commands import recommend as recommend_cmd
from concierge_cli.commands import request_tool as request_tool_cmd
from concierge_cli.errors import ConciergeCliError, ServiceUnreachableError


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="concierge",
        description="Concierge CLI — thin HTTP shim over the Concierge service.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"concierge {__version__}",
    )

    subparsers = parser.add_subparsers(dest="subcommand", metavar="<subcommand>")
    recommend_cmd.register(subparsers)
    request_tool_cmd.register(subparsers)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help(sys.stderr)
        return 2

    try:
        return args.func(args)
    except ConciergeCliError as exc:
        print(exc.user_message, file=sys.stderr)
        return exc.exit_code
    except httpx.TransportError:
        url = os.environ.get("CONCIERGE_URL", DEFAULT_BASE_URL)
        fallback = ServiceUnreachableError(url)
        print(fallback.user_message, file=sys.stderr)
        return fallback.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
