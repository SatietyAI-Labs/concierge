"""Concierge shim-script generator + PATH-visibility checker (Day 6 Option 3).

Per DECISIONS `[2026-04-27 Day 6]` Decision A:

- Shim location: `~/.concierge/bin/` (unambiguously Concierge-owned;
  no collision with pre-Option-3 `pip install --user` artifacts at
  `~/.local/bin/`)
- Shims are bash one-liners that exec the venv-installed binary with
  `"$@"` arg passthrough; chmod 0o755
- Runtime PATH-visibility check warns the operator if
  `~/.concierge/bin/` is not on PATH (called by `install_pip_user`
  after a successful install)
- Shell detection is intentionally narrow: bash/zsh/fallback only.
  Fish, nushell, PowerShell, and other non-POSIX shells fall back to
  `~/.profile` with an explanatory "may not read this" note rather
  than silently picking the wrong rc file. **A future contributor
  MUST NOT expand the shell-detection helper without a real-world
  signal that justifies the additional surface area** — the
  DECISIONS entry is explicit about that.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)


CONCIERGE_HOME_DIR_NAME = ".concierge"
CONCIERGE_BIN_DIR_NAME = "bin"


_SHIM_TEMPLATE = """#!/usr/bin/env bash
exec "{target}" "$@"
"""


def _concierge_bin_dir(home: Optional[Path] = None) -> Path:
    """Resolve the Concierge-owned shim directory at
    `<home>/.concierge/bin/`. Defaults to `Path.home()` when None —
    explicit-parameter pattern matches `_ensure_concierge_venv`.
    """
    if home is None:
        home = Path.home()
    return home / CONCIERGE_HOME_DIR_NAME / CONCIERGE_BIN_DIR_NAME


def _generate_shim(
    tool_name: str,
    venv: Path,
    *,
    home: Optional[Path] = None,
) -> Path:
    """Write a bash shim at `<home>/.concierge/bin/<tool_name>` that
    exec's the venv-installed binary at `<venv>/bin/<tool_name>` with
    full positional + named arg passthrough.

    Idempotent: re-running with the same args overwrites the existing
    shim cleanly (no append corruption). The shim is `chmod 0o755`.

    Parameters:
        tool_name: The catalog slug / executable name (e.g. "csvkit").
                   Becomes both the shim filename and the venv binary
                   target.
        venv: The Concierge-managed venv root path (typically the
              return value of `_ensure_concierge_venv()`). Shim
              targets `<venv>/bin/<tool_name>`.
        home: Operator's home directory. Defaults to `Path.home()`
              when None — testability seam.

    Returns:
        Path to the generated shim file.
    """
    bin_dir = _concierge_bin_dir(home)
    bin_dir.mkdir(parents=True, exist_ok=True)

    shim_path = bin_dir / tool_name
    target = venv / "bin" / tool_name

    shim_path.write_text(_SHIM_TEMPLATE.format(target=str(target)))
    shim_path.chmod(0o755)

    logger.info(
        "shim.generate tool=%s shim=%s target=%s",
        tool_name, shim_path, target,
    )
    return shim_path


def _check_path_visibility(*, home: Optional[Path] = None) -> Optional[str]:
    """Check whether `<home>/.concierge/bin/` is on the operator's
    PATH. Returns None if visible (no warning needed); otherwise
    returns a warning string with a copy-pasteable PATH-addition
    instruction.

    Shell detection uses `$SHELL` env var:
    - bash → `~/.bashrc`
    - zsh → `~/.zshrc`
    - anything else (including unset / unrecognized) → `~/.profile`
      with an "if your shell doesn't read `~/.profile`, add this line
      to your shell's startup file" note

    Per Decision A: intentionally narrow scope. Do not expand to
    fish/nushell/PowerShell without a real-world signal.
    """
    bin_dir = _concierge_bin_dir(home)

    # PATH visibility: split PATH env var by os.pathsep, compare each
    # entry as a Path object against bin_dir (handles trailing-slash
    # normalization correctly).
    path_env = os.environ.get("PATH", "")
    path_entries = [p for p in path_env.split(os.pathsep) if p]
    for entry in path_entries:
        if Path(entry) == bin_dir:
            return None

    # Not on PATH — build the shell-detected warning + instruction
    shell = os.environ.get("SHELL", "")
    shell_name = Path(shell).name if shell else ""

    if shell_name == "bash":
        rc_file = "~/.bashrc"
        rc_note = ""
    elif shell_name == "zsh":
        rc_file = "~/.zshrc"
        rc_note = ""
    else:
        rc_file = "~/.profile"
        rc_note = (
            " (if your shell doesn't read ~/.profile, add this line to "
            "your shell's startup file instead)"
        )

    instruction = f'echo \'export PATH="{bin_dir}:$PATH"\' >> {rc_file}'

    return (
        f"note: {bin_dir} not on PATH; Concierge-installed tools "
        f"won't be invokable until you add it{rc_note}. Run: {instruction}"
    )
