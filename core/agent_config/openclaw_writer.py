"""openclaw.json config mutator for the eventual `concierge enable/
disable <agent> <tool>` CLI subcommands.

Stage 1A item 6. Pure JSON config mutator: reads an agent's
openclaw.json, writes a sibling `.bak` of the previous content, applies
one `mcp.servers` change in memory, atomic-writes the new file via
tempfile + `os.replace`.

Scope
-----
- One `mcp.servers` entry per call: insert/replace (enable) or remove
  (disable). Caller iterates if multi-server fan-out is needed.
- Atomic write only — does not restart the agent, does not validate
  the server_config payload's shape, does not look up the catalog to
  decide which config to inject. The catalog → server_config lookup
  is item 1b's `concierge enable` CLI subcommand concern; this module
  treats `server_config` as opaque JSON.

`.bak` discipline
-----------------
Only the most recent `.bak` survives — each write overwrites any
prior `.bak`. Per-stage rollback substrate lives in
`~/.satiety-snapshots/<stage>-complete-YYYYMMDD/` per CLAUDE.md §3;
the `.bak` sibling is a most-recent-write convenience, not a long-
term audit trail. Matches the master-plan-v1.1 §III.2 item 6 literal
text ("a sibling `.bak` file", singular).

Placement deviation
-------------------
Plan literal text reads `core/install/openclaw_writer.py`. Per items-
5+6 Decision 5 (revised), this lives at `core/agent_config/
openclaw_writer.py` — the openclaw.json writer is a host-platform
config mutator, not a package installer; `core/install/` is reserved
for pip/npm/pipx/venv work. Naming honesty is load-bearing for a
publicly-released product; the deviation lands as an entry in
DECISIONS at items-5+6 close.

Atomic-write idiom
------------------
`_atomic_write` is duplicated locally from
`core/lifecycle_store/writer.py::_atomic_write` per items-5+6
Decision 7. Two consumers of a ~15-line idiom is fine; if a third
surfaces, extract to `core/util/atomic.py` then.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Optional


logger = logging.getLogger(__name__)


# Codename → openclaw.json path. Strict 5-agent set; functional-name
# resolution lives here so callers pass codenames (CLAUDE.md §2
# convention). New agents land by extending this map + the
# exhaustiveness test in `tests/test_openclaw_writer.py`.
AGENT_PATHS: dict[str, Path] = {
    "alfred":   Path.home() / ".openclaw" / "openclaw.json",
    "scout":    Path.home() / ".openclaw-content" / "openclaw.json",
    "dispatch": Path.home() / ".openclaw-distribution" / "openclaw.json",
    "radar":    Path.home() / ".openclaw-intelligence" / "openclaw.json",
    "bridge":   Path.home() / ".openclaw-engagement" / "openclaw.json",
}


class UnknownAgentError(ValueError):
    """Raised when `set_mcp_server` is called with an agent_id outside
    the 5-codename set. Distinct from `FileNotFoundError` so callers
    can tell "no agent named that" apart from "the agent exists but
    their config file isn't on disk."
    """


def _resolve_agent_path(agent_id: str) -> Path:
    if agent_id not in AGENT_PATHS:
        raise UnknownAgentError(
            f"agent_id {agent_id!r} is not in the AGENT_PATHS set "
            f"(known: {sorted(AGENT_PATHS)})"
        )
    return AGENT_PATHS[agent_id]


def _atomic_write(path: Path, content: str) -> None:
    """Write `content` to `path` atomically via tempfile + `os.replace`.

    Duplicated from `core/lifecycle_store/writer.py::_atomic_write`
    per items-5+6 Decision 7. Same-directory tempfile so `os.replace`
    is a same-filesystem rename and no reader ever sees a partial
    write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path_str = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fp:
            fp.write(content)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def set_mcp_server(
    agent_id: str,
    server_name: str,
    server_config: Optional[dict[str, Any]],
    *,
    config_path: Optional[Path] = None,
) -> None:
    """Insert/replace (enable) or remove (disable) one entry under
    `mcp.servers` in an agent's openclaw.json.

    Parameters
    ----------
    agent_id
        One of the 5 codenames in `AGENT_PATHS`. Functional-name
        resolution happens here so callers stay codename-only.
    server_name
        Key under `mcp.servers` (e.g. `"memory"`, `"firefox"`).
    server_config
        Dict to install at `mcp.servers[server_name]`. `None` means
        disable (remove the entry). The dict is treated as opaque JSON
        — schema validation is the caller's concern.
    config_path
        Optional override for the resolved path. Tests pass a
        `tmp_path` fixture here; live callers pass `None` and get
        `AGENT_PATHS[agent_id]`.

    Behavior
    --------
    - Enable (`server_config` not None): inserts a new key, or
      replaces an existing one. Pre-write `.bak` rotated to current
      content; new file atomic-written.
    - Disable (`server_config is None`): removes the key if present.
      On already-absent, returns a pure no-op (no write, no `.bak`
      rotation) — idempotency preserves operator audit clarity.

    Missing parent keys (`mcp` or `mcp.servers`) on enable are
    created. Removing the last server leaves an empty
    `mcp.servers: {}` rather than deleting the nested key — preserves
    the file's structural shape for any consumer that grep-checks for
    `mcp.servers` presence.

    Raises
    ------
    UnknownAgentError
        `agent_id` not in `AGENT_PATHS`.
    FileNotFoundError
        Config file does not exist at the resolved path.
    json.JSONDecodeError
        Existing file is not valid JSON (re-raised with the file path
        included in the message for operator triage).
    """
    if config_path is None:
        config_path = _resolve_agent_path(agent_id)

    if not config_path.exists():
        raise FileNotFoundError(f"openclaw.json not found at {config_path}")

    raw = config_path.read_text(encoding="utf-8")
    try:
        config = json.loads(raw)
    except json.JSONDecodeError as exc:
        # Re-raise with the file path attached so an operator reading
        # the error sees which config failed to parse without needing
        # to inspect the traceback's frames.
        raise json.JSONDecodeError(
            f"{exc.msg} (file: {config_path})", exc.doc, exc.pos
        ) from None

    mcp = config.setdefault("mcp", {})
    servers = mcp.setdefault("servers", {})

    if server_config is None:
        if server_name not in servers:
            logger.info(
                "openclaw_writer.disable_noop agent=%s server=%s path=%s "
                "— already absent, no write performed",
                agent_id, server_name, config_path,
            )
            return
        del servers[server_name]
        action = "disable"
    else:
        action = "replace" if server_name in servers else "enable"
        servers[server_name] = server_config

    # Backup previous content. .bak is overwritten on each write per
    # items-5+6 Decision 8.
    bak_path = config_path.with_suffix(config_path.suffix + ".bak")
    _atomic_write(bak_path, raw)

    # 2-space indent matches the live openclaw.json shape (verified
    # 2026-05-14 against ~/.openclaw/openclaw.json and worker configs).
    # Trailing newline for POSIX-text-file tidiness.
    new_content = json.dumps(config, indent=2) + "\n"
    _atomic_write(config_path, new_content)

    logger.info(
        "openclaw_writer.%s agent=%s server=%s path=%s",
        action, agent_id, server_name, config_path,
    )
