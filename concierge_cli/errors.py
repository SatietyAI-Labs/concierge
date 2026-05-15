"""Error hierarchy + exit-code map for the concierge CLI.

The five categories below match the contract in master-plan-v1.1.md
§III. Each exception subclass carries a class-level `exit_code` (the
process return code) and a `user_message` property (the line printed
to stderr). Exit codes 0, 1, 2 are reserved for: success, generic
fallback, and argparse usage errors.
"""
from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import Any


class ConciergeCliError(Exception):
    """Base class — subclasses set `exit_code` and override `user_message`."""

    exit_code: int = 1

    @property
    def user_message(self) -> str:
        raise NotImplementedError


class UsageError(ConciergeCliError):
    """Client-side validation / local-precondition failure — surfaces at
    exit 2, the argparse usage-error convention.

    Distinct from the ServiceError taxonomy (exits 3/4/5/6) so the
    operator-facing error contract stays legible: 2 means "the command
    could not be carried out as given — fix something locally and
    retry," 3-6 mean "the HTTP service is the problem."

    Shared across subcommands. `concierge request-tool` (Stage 1A item
    5) carried a private `_UsageError`; `concierge enable/disable`
    (item 1b) needs the same class, so it is promoted here per the
    D51 forward-carry ("when extending `concierge_cli.errors`...").

    Mirrors the descriptor shape of every other subclass: the base
    `user_message` is a property without a setter, so the underlying
    string is stored as a plain attribute and `user_message` is
    overridden as a property (assigning `self.user_message = ...`
    raises AttributeError — see D51).
    """

    exit_code = 2

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self._message = message

    @property
    def user_message(self) -> str:
        return f"concierge: {self._message}"


class ServiceUnreachableError(ConciergeCliError):
    """TCP connect failed (or connect-timed-out) twice in a row."""

    exit_code = 3

    def __init__(self, url: str) -> None:
        super().__init__(f"cannot reach service at {url}")
        self.url = url

    @property
    def user_message(self) -> str:
        return (
            f"concierge: cannot reach service at {self.url} — is it running? "
            "(try: systemctl --user status concierge.service)"
        )


class ServiceTimeoutError(ConciergeCliError):
    """Server-side work was in flight; no retry (avoid double-billing)."""

    exit_code = 4

    def __init__(self, timeout_seconds: float) -> None:
        super().__init__(f"read timeout after {timeout_seconds}s")
        self.timeout_seconds = timeout_seconds

    @property
    def user_message(self) -> str:
        return (
            f"concierge: request timed out after {self.timeout_seconds:.0f}s "
            "(cold start? retry, or raise --timeout)"
        )


class ServiceError(ConciergeCliError):
    """Non-2xx response. Handles two body shapes (FastAPI default + structured)."""

    # Concierge endpoints emit `{"detail": {"error": "<slug>", "message": "..."}}`
    # at the HTTPException boundary (see core/api/recommend.py:142-160). FastAPI's
    # default is `{"detail": "<string>"}`. The user_message extraction below
    # handles both shapes plus the unknown-dict fallback.

    exit_code = 5

    def __init__(self, status: int, detail: Any) -> None:
        super().__init__(f"service returned {status}")
        self.status = status
        self.detail = detail

    @property
    def user_message(self) -> str:
        prefix = f"concierge: service returned {self.status}"
        if isinstance(self.detail, dict):
            try:
                return f"{prefix} {self.detail['error']}: {self.detail['message']}"
            except (KeyError, TypeError):
                return f"{prefix}: {json.dumps(self.detail)}"
        if isinstance(self.detail, str):
            return f"{prefix}: {self.detail}"
        if self.detail is None:
            return prefix
        return f"{prefix}: {self.detail!r}"


class MalformedResponseError(ConciergeCliError):
    """2xx response whose body did not parse — raw saved to a tmpfile."""

    exit_code = 6

    def __init__(self, tmpfile_path: Path) -> None:
        super().__init__(f"malformed response saved to {tmpfile_path}")
        self.tmpfile_path = tmpfile_path

    @classmethod
    def capture(cls, raw_body: Any) -> "MalformedResponseError":
        """Write raw_body to a tmpfile; return an instance pointing at it.

        Side effect at construction time is deliberate: if the exception
        exists, the tmpfile exists. Avoids the "we said we wrote it but
        threw mid-flight" failure mode.
        """
        ts = int(time.time())
        path = Path(tempfile.gettempdir()) / f"concierge-malformed-{ts}.json"
        try:
            payload = json.dumps(raw_body, indent=2, default=repr)
        except (TypeError, ValueError):
            payload = repr(raw_body)
        path.write_text(payload, encoding="utf-8")
        return cls(tmpfile_path=path)

    @property
    def user_message(self) -> str:
        return (
            "concierge: service returned an unexpected response shape; "
            f"raw body at {self.tmpfile_path}"
        )
