"""Agent-side config mutators.

This package owns operations that mutate an AI agent's host-platform
configuration files — distinct from `core/install/` (which installs
packages onto disk) and from `core/lifecycle_store/` (which manages
Concierge's own pending/resolved/archived request files).

Stage 1A item 6 ships the first module: `openclaw_writer.py`, an
OpenClaw `openclaw.json` config mutator backing the eventual
`concierge enable/disable <agent> <tool>` CLI subcommands (item 1b).

Future modules in this package will land at Stage 1B Gate 5 (SOUL.md
/ SKILL.md surgical rewriters) and as additional host platforms join
the fleet — keeping host-platform config writers neighborly is the
package's organizing intent.

Placement deviates from master-plan-v1.1 §III.2 item 6 literal text
(`core/install/openclaw_writer.py`) per items-5+6 Decision 5
(revised) — `core/install/` is package-installers (pip/npm/pipx/venv)
and the openclaw.json writer is a JSON config mutator with no install
verb. Naming honesty for a publicly-released product.
"""
from core.agent_config.openclaw_writer import (
    AGENT_PATHS,
    UnknownAgentError,
    set_mcp_server,
)


__all__ = [
    "AGENT_PATHS",
    "UnknownAgentError",
    "set_mcp_server",
]
