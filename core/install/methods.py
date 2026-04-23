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
    """Install a Python package to the user site via `pip install --user`.

    The `--user` flag routes the install to `~/.local/` without
    needing sudo and without polluting system site-packages.
    """
    cmd = ["pip", "install", "--user", package]
    return _run(METHOD_PIP_USER, cmd, timeout_seconds)


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
