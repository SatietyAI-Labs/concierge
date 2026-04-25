"""Three low-level subprocess-wrapped installers.

Each installer:

1. Constructs a no-sudo install command per the SOUL-delta
   `## Requesting Capabilities` targets.
2. Runs the command via `subprocess.run` with a bounded timeout.
3. Wraps OSError / TimeoutExpired as a returncode=-1 failure so
   callers never have to catch subprocess exceptions.
4. Returns an `InstallResult` with the canonical method key and
   the reconstructed command string for operator audit.

No installer mutates lifecycle state. No installer writes logs at
any level above DEBUG (the caller owns log level — install
attempts are operationally interesting events worth INFO-logging
*by the caller*, not here).
"""
from __future__ import annotations

import logging
import shlex
import subprocess
import time
from pathlib import Path

from core.install.schemas import InstallResult
from core.install.shims import _check_path_visibility, _generate_shim
from core.install.venv import ConciergeVenvError, _ensure_concierge_venv


logger = logging.getLogger(__name__)


DEFAULT_NPM_TIMEOUT = 60.0
DEFAULT_PIP_TIMEOUT = 60.0
DEFAULT_BINARY_TIMEOUT = 120.0
DEFAULT_NPX_MCP_TIMEOUT = 45.0

METHOD_NPM_GLOBAL = "npm_global"
METHOD_PIP_USER = "pip_user"
METHOD_SINGLE_BINARY = "single_binary"
METHOD_NPX_MCP = "npx_mcp"


def install_npm_global(package: str, *, timeout_seconds: float = DEFAULT_NPM_TIMEOUT) -> InstallResult:
    """Install an npm package at user scope via `npm install -g`.

    Assumes the user's npm prefix is configured to a writable path
    (typically `~/.npm-global`). X13 does not set the prefix — that
    is an environment-setup concern upstream of the install call.
    """
    cmd = ["npm", "install", "-g", package]
    return _run(METHOD_NPM_GLOBAL, cmd, timeout_seconds)


def install_pip_user(package: str, *, timeout_seconds: float = DEFAULT_PIP_TIMEOUT) -> InstallResult:
    """Install a Python package into the Concierge-managed venv at
    `~/.concierge/tools-venv/`.

    Day 6 Option 3 (DECISIONS `[2026-04-27 Day 6]`): PEP-668 sidestep
    via a Concierge-owned venv. Lazy bootstrap on first call —
    `_ensure_concierge_venv()` creates the venv if it doesn't exist,
    then returns the venv path immediately on every subsequent call
    (idempotent fast path).

    The METHOD_PIP_USER name is preserved for backward compatibility
    with existing catalog rows and the `normalize_install_method`
    dispatcher; the *behavior* changed (pip-via-venv instead of
    `pip --user`), the canonical method key did not.

    On `ConciergeVenvError` (venv bootstrap failure — e.g. stdlib
    venv missing, disk full, partial venv state), the function
    returns `InstallResult(success=False, ...)` carrying the
    bootstrap diagnostic, mirroring the existing X13 "subprocess
    failures collapse to typed failure objects" rule. Caller sees
    the same shape regardless of whether the failure is in venv
    bootstrap or in the actual pip subprocess.
    """
    try:
        venv = _ensure_concierge_venv()
    except ConciergeVenvError as exc:
        # Synthetic command string for audit consistency — the would-be
        # pip command never ran, but the operator's audit trail should
        # still show what was attempted.
        synthetic_cmd = (
            f"<concierge-venv>/bin/pip install {shlex.quote(package)} "
            f"(venv bootstrap failed)"
        )
        logger.info(
            "install.%s.venv_bootstrap_failed package=%s error=%s",
            METHOD_PIP_USER, package, exc,
        )
        return InstallResult(
            method=METHOD_PIP_USER,
            command=synthetic_cmd,
            success=False,
            returncode=-1,
            stdout="",
            stderr=f"ConciergeVenvError: {exc}",
            elapsed_ms=0,
        )

    cmd = [str(venv / "bin" / "pip"), "install", package]
    result = _run(METHOD_PIP_USER, cmd, timeout_seconds)

    if not result.success:
        return result

    # Post-install: generate the operator-facing shim at
    # ~/.concierge/bin/<package> and check whether that directory is
    # on PATH. Both are non-fatal — a shim-generation failure or a
    # PATH-visibility warning leaves the install succeeded but appends
    # diagnostic text to stderr so the operator sees it via the
    # lifecycle markdown / install record.
    extra_stderr: list[str] = []
    try:
        _generate_shim(package, venv)
    except Exception as exc:
        logger.warning(
            "install.%s.shim_generate_failed package=%s error=%s",
            METHOD_PIP_USER, package, exc,
        )
        extra_stderr.append(f"(shim generation failed: {exc})")

    path_warning = _check_path_visibility()
    if path_warning:
        extra_stderr.append(path_warning)

    if not extra_stderr:
        return result

    merged_stderr = result.stderr
    for line in extra_stderr:
        merged_stderr = (merged_stderr + "\n" + line) if merged_stderr else line
    return InstallResult(
        method=result.method,
        command=result.command,
        success=result.success,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=merged_stderr,
        elapsed_ms=result.elapsed_ms,
    )


def install_npx_mcp(
    package: str, *, timeout_seconds: float = DEFAULT_NPX_MCP_TIMEOUT
) -> InstallResult:
    """Verify an npx-launched MCP package is resolvable on the npm
    registry. Uses `npm view <package> name` — a read-only query
    that confirms the package exists without actually prefetching
    or executing anything.

    The full "install" story for npx-MCP tools is that the package
    runs on-demand via `npx -y <package>` when an MCP client
    connects — there is no permanent global install. Registering
    the MCP server with Claude Code's runtime config is the
    adapter's concern (backing_server_registry), not X13's. X13's
    contract here is: confirm the package is reachable so first-
    load won't fail on a typo'd or nonexistent package.

    Live `npx` prefetch is explicitly deferred — the soak phase may
    promote this to a warmer command if registry-check proves
    insufficient.
    """
    cmd = ["npm", "view", package, "name"]
    return _run(METHOD_NPX_MCP, cmd, timeout_seconds)


def install_single_binary(
    url: str,
    dest_path: str,
    *,
    timeout_seconds: float = DEFAULT_BINARY_TIMEOUT,
) -> InstallResult:
    """Download a single binary to `dest_path` and make it executable.

    Uses `curl -fL -o <dest> <url>` followed by `chmod +x <dest>`
    via a shell one-liner so the failure of either stage surfaces
    as a non-zero returncode. `dest_path` is resolved (home `~`
    expansion) before the command is constructed; callers that pass
    absolute paths get them through unchanged.
    """
    resolved = str(Path(dest_path).expanduser())
    Path(resolved).parent.mkdir(parents=True, exist_ok=True)
    # Shell one-liner — both curl AND chmod must succeed. shlex.quote
    # on the arguments prevents injection if url/dest contains spaces
    # or metacharacters.
    shell_cmd = (
        f"curl -fL -o {shlex.quote(resolved)} {shlex.quote(url)} "
        f"&& chmod +x {shlex.quote(resolved)}"
    )
    return _run_shell(METHOD_SINGLE_BINARY, shell_cmd, timeout_seconds)


# ---- Private runners -----------------------------------------------------


def _run(method: str, cmd: list[str], timeout_seconds: float) -> InstallResult:
    """Execute a command list via subprocess.run. OSError and
    TimeoutExpired both collapse to returncode=-1 failure results
    so callers never catch subprocess exceptions.
    """
    command_str = " ".join(shlex.quote(arg) for arg in cmd)
    logger.debug("install.%s.start command=%s timeout=%.1f", method, command_str, timeout_seconds)
    start = time.monotonic()
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.debug("install.%s.not_found error=%s", method, exc)
        return InstallResult(
            method=method,
            command=command_str,
            success=False,
            returncode=-1,
            stdout="",
            stderr=f"command not found: {cmd[0]}",
            elapsed_ms=elapsed_ms,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.debug("install.%s.timeout elapsed_ms=%d", method, elapsed_ms)
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return InstallResult(
            method=method,
            command=command_str,
            success=False,
            returncode=-1,
            stdout=stdout,
            stderr=stderr + f"\n(timed out after {timeout_seconds:.1f}s)",
            elapsed_ms=elapsed_ms,
        )
    except OSError as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.debug("install.%s.os_error error=%s", method, exc)
        return InstallResult(
            method=method,
            command=command_str,
            success=False,
            returncode=-1,
            stdout="",
            stderr=f"OSError: {exc}",
            elapsed_ms=elapsed_ms,
        )

    elapsed_ms = int((time.monotonic() - start) * 1000)
    return InstallResult(
        method=method,
        command=command_str,
        success=completed.returncode == 0,
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        elapsed_ms=elapsed_ms,
    )


def _run_shell(method: str, shell_cmd: str, timeout_seconds: float) -> InstallResult:
    """Variant of `_run` for shell-string commands (needed for
    single_binary's `curl && chmod` one-liner). Same failure-class
    handling as `_run`.
    """
    logger.debug("install.%s.start shell=%s timeout=%.1f", method, shell_cmd, timeout_seconds)
    start = time.monotonic()
    try:
        completed = subprocess.run(
            shell_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return InstallResult(
            method=method,
            command=shell_cmd,
            success=False,
            returncode=-1,
            stdout=stdout,
            stderr=stderr + f"\n(timed out after {timeout_seconds:.1f}s)",
            elapsed_ms=elapsed_ms,
        )
    except OSError as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return InstallResult(
            method=method,
            command=shell_cmd,
            success=False,
            returncode=-1,
            stdout="",
            stderr=f"OSError: {exc}",
            elapsed_ms=elapsed_ms,
        )

    elapsed_ms = int((time.monotonic() - start) * 1000)
    return InstallResult(
        method=method,
        command=shell_cmd,
        success=completed.returncode == 0,
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        elapsed_ms=elapsed_ms,
    )
