"""Concierge-managed venv bootstrap helper (Day 6 Option 3).

PEP-668 sidestep: Python tool installs go into a Concierge-owned venv
at `~/.concierge/tools-venv/` so Concierge isn't touching system
Python. Works identically on PEP-668 distros, Homebrew Python, and
dev machines with operator's own venvs (the tools-venv is isolated
from all of them via stdlib's default no-system-site-packages).

The helper is the single seam where venv creation happens. Called
lazily from `install_pip_user` on every install — first call
bootstraps the venv (~1-3s on stdlib `python3 -m venv`), every
subsequent call hits the idempotent fast path.

Direct-create-at-final-path pattern: the venv is created directly at
`<home>/.concierge/tools-venv/`, not via a `.tmp` staging dir. Python's
`venv` module hard-codes the absolute venv path into the shebangs of
`bin/pip`, `bin/pip3`, etc., and into `pyvenv.cfg`'s `home=` field —
which means a post-creation rename leaves all those paths stale and
breaks pip invocation. Standard Python venv usage is "create at final
path; never move."

On `subprocess.run` failure (returncode != 0), the partial venv state
is `shutil.rmtree`'d before raising `ConciergeVenvError` — the
operator gets a clean slate to retry from. Hard-crash mid-creation
(SIGKILL etc.) leaves the partial state on disk; the next call's
"incomplete venv — remove manually" guard handles that recovery path.

See DECISIONS `[2026-04-27 Day 6]`:
- "Concierge-managed venv creator: stdlib `python3 -m venv`" — this
  module's contract (revised post-Step-5 to drop the
  `--system-site-packages=False` flag and the `.tmp`-rename pattern)
- "Option 3 scope (Python tools only) + migration approach" — this
  helper is invoked only from `install_pip_user`
- "Concierge-managed venv shim location: ~/.concierge/bin/" —
  separate module's concern; this helper only manages tools-venv/
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)


CONCIERGE_HOME_DIR_NAME = ".concierge"
TOOLS_VENV_DIR_NAME = "tools-venv"


class ConciergeVenvError(Exception):
    """Raised when the Concierge-managed venv cannot be bootstrapped.

    Carries the underlying subprocess stderr (or other diagnostic)
    in the message so the caller in `install_pip_user` can convert
    to `InstallResult(success=False, stderr=<diagnostic>)` without
    losing the underlying error.
    """


def _ensure_concierge_venv(home: Optional[Path] = None) -> Path:
    """Ensure the Concierge-managed venv exists at
    `<home>/.concierge/tools-venv/`. Returns the venv root path.

    Idempotent: if the venv already exists (marker: `bin/python`
    invokable), returns the path immediately without subprocess
    invocation. This is the load-bearing fast path — every install
    after the first hits this branch.

    Direct creation at final path: bootstrap runs `python3 -m venv
    <venv>` against the canonical location, not a staging dir. On
    subprocess failure (returncode != 0), the partial venv is
    `shutil.rmtree`'d before raising. Hard-crash mid-creation leaves
    partial state on disk; the next call's "incomplete venv" guard
    asks the operator to remove it manually.

    Parameters:
        home: Operator's home directory. Defaults to `Path.home()`
              when None. The explicit parameter is the testability
              seam — tests pass `tmp_path` to avoid touching real
              `~/.concierge/`.

    Returns:
        Path to the venv root (e.g. `<home>/.concierge/tools-venv/`).
        Caller constructs paths like `<root>/bin/pip` from this.

    Raises:
        ConciergeVenvError: when `subprocess.run` fails (nonzero
            returncode), OR when the venv is in a partially-broken
            state (`<venv>/` exists but `bin/python` doesn't —
            requires manual operator cleanup before retrying; the
            helper does NOT silently rmtree because the operator
            may have manually placed work there).
    """
    if home is None:
        home = Path.home()

    concierge_home = home / CONCIERGE_HOME_DIR_NAME
    venv = concierge_home / TOOLS_VENV_DIR_NAME
    venv_python = venv / "bin" / "python"

    # Fast path: venv exists + invokable
    if venv_python.exists():
        logger.debug("venv.ensure.already_present path=%s", venv)
        return venv

    # Defensive: <venv>/ exists but bin/python doesn't. Partially-
    # broken state from a prior hard-crash mid-creation (SIGKILL etc.)
    # or operator intervention. Don't silently rmtree — operator may
    # have manually placed work there. Make the cleanup explicit.
    if venv.exists():
        raise ConciergeVenvError(
            f"Concierge-managed venv at {venv} exists but is incomplete "
            f"(no bin/python). Remove it manually before retrying: "
            f"`rm -rf {venv}`"
        )

    # Bootstrap parent dir (~/.concierge/) if missing
    concierge_home.mkdir(parents=True, exist_ok=True)

    # Create the venv directly at the final path. Decision B contract
    # (revised post-Step-5):
    #
    # - sys.executable, no `--system-site-packages` flag (stdlib
    #   default is isolation; the flag is opt-IN store_true semantics,
    #   no `=False` form exists). Regression-guard test asserts
    #   `--system-site-packages` is NOT in argv so a future contributor
    #   who tries to opt INTO system-site-packages trips it.
    #
    # - No `.tmp` staging + rename: Python venv hard-codes the absolute
    #   venv path into bin/pip's shebang and pyvenv.cfg's home= field;
    #   renaming breaks both. Standard Python venv usage is "create at
    #   final path; never move."
    cmd = [
        sys.executable,
        "-m",
        "venv",
        str(venv),
    ]
    logger.info(
        "venv.ensure.bootstrap python=%s target=%s",
        sys.executable,
        venv,
    )
    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )

    if completed.returncode != 0:
        # Best-effort cleanup of partial venv state before raising —
        # operator gets a clean slate to retry from.
        shutil.rmtree(venv, ignore_errors=True)
        stderr = (completed.stderr or "").strip()
        raise ConciergeVenvError(
            f"Concierge venv bootstrap failed "
            f"(returncode={completed.returncode}): {stderr}"
        )

    logger.info("venv.ensure.bootstrap_complete path=%s", venv)
    return venv
