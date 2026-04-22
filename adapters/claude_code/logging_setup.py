"""Stderr-only logging for the shim.

The operational invariant: **stdout is reserved for JSON-RPC 2.0
framing**. A single log line leaking to stdout contaminates the
protocol stream and kills the Claude Code MCP client. The shim's
logger setup runs BEFORE any other module code so no logger-on-
import side effect can touch stdout.

The print-lint test (`tests/test_shim_print_lint.py`) is the
complementary static check: no `print(` calls anywhere under
`adapters/claude_code/`. This module is the dynamic check — the
runtime logger configuration.
"""
from __future__ import annotations

import logging
import sys


def configure_stderr_logging(level: str = "DEBUG") -> None:
    """Install a stderr-only handler on the root logger and remove
    any preexisting handlers (including ones that might default to
    stdout).

    Idempotent — safe to call multiple times. The shim calls this
    at entry point before anything else runs.
    """
    numeric_level = getattr(logging, level.upper(), logging.DEBUG)

    root = logging.getLogger()
    root.setLevel(numeric_level)
    # Remove every existing handler; we want a known-clean state
    # regardless of how the process was launched.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(numeric_level)
    stderr_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(stderr_handler)
