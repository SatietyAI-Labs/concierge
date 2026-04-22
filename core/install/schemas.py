"""Structured result for one install attempt.

`InstallResult` is the single return shape from every X13 installer.
It carries enough detail for the caller to (a) apply the correct
lifecycle follow-up transition, (b) log operationally, and (c)
surface the command + output to the operator via the UI or soak
log without a re-run.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InstallResult:
    """One install attempt's outcome.

    `method`        canonical method key (e.g. `npm_global`,
                    `pip_user`, `single_binary`); a stable string
                    the UI and log consumer can switch on.
    `command`       the exact shell command executed, as a
                    single-string re-rendering. Operator-auditable;
                    not re-executable via shell (may contain
                    already-quoted args).
    `success`       True iff subprocess returncode was 0 AND no
                    OSError was raised. Drives the lifecycle
                    follow-up transition (installed vs failed).
    `returncode`    subprocess returncode, or -1 on OSError
                    (command not found, permission denied, etc.).
    `stdout`        captured stdout (utf-8-decoded, errors=replace).
    `stderr`        captured stderr (utf-8-decoded, errors=replace).
    `elapsed_ms`    wall-clock milliseconds for the subprocess call.
    """

    method: str
    command: str
    success: bool
    returncode: int
    stdout: str
    stderr: str
    elapsed_ms: int
