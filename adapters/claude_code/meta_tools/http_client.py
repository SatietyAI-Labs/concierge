"""Shared httpx AsyncClient for Concierge meta-tool handlers.

Lazy-initialized on first handler call. One client per shim process
for connection pooling. Explicit `aclose()` is wired into the shim's
`main()` finally-block so shutdown under SIGTERM or abrupt process
exit does not leak a warning like *"AsyncClient used without
explicit close"* into the soak-phase log stream.

Configuration is env-only (no pydantic settings class — one variable
does not warrant one):

    CONCIERGE_URL       Backing service base URL. Default:
                        http://127.0.0.1:8000 (single-process
                        assumption, same as scripts/concierge-shim
                        docstring).

Base URL is captured at first-call time; a subsequent env change
does NOT take effect until the shim restarts. This is intentional —
a long-lived shim session with a shifting backing target would be
surprising.
"""
from __future__ import annotations

import os
from typing import Optional

import httpx


DEFAULT_CONCIERGE_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SECONDS = 30.0

_client: Optional[httpx.AsyncClient] = None


def get_concierge_url() -> str:
    return os.environ.get("CONCIERGE_URL", DEFAULT_CONCIERGE_URL)


def get_client() -> httpx.AsyncClient:
    """Return the shared AsyncClient, creating it on first call."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=get_concierge_url(),
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
    return _client


async def aclose() -> None:
    """Close the shared AsyncClient if it was ever constructed. Safe
    to call in a finally-block regardless of whether any handler ran
    during the shim's lifetime.
    """
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def set_client_for_tests(client: Optional[httpx.AsyncClient]) -> None:
    """Inject a test client (typically with `httpx.MockTransport`)
    and reset to a clean state when tests pass `None`. Test-only
    surface; production code paths do not touch this.
    """
    global _client
    _client = client
