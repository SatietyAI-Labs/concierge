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

## Timeout sizing

`DEFAULT_TIMEOUT_SECONDS = 90.0`. Sized for the Concierge service's
cold-start tax on its first `POST /recommend` call: the service
initializes sentence-transformers (model load, ~2-5s) and
ChromaDB (first collection query, ~1-3s) on the first memory
lookup, and the subsequent Anthropic API call at `effort=xhigh`
frequently runs 10-30s end-to-end. Adding headroom for slow
networks + first-call GC, 90s is the point where any legitimate
Concierge call has completed and a longer wait is signal of a
genuinely hung service.

Post-warm-up calls typically complete in 5-15s. The 90s timeout
is upper-bound only — not a latency target.

## Deferred soak-phase optimization: pre-warm

The cold-start tax is concentrated on the first call. A uvicorn
startup hook that eagerly loads sentence-transformers + warms the
ChromaDB collection would shift the tax into service-startup
latency (which is not user-visible) and keep first-call latency
below 15s. Not fixed here; candidate for Day-5-or-later soak-phase
optimization per the 2026-04-22 moneyshot DECISIONS entry. The
90s timeout makes the pre-warm unnecessary for correctness — it's
a latency optimization, not a reliability fix.
"""
from __future__ import annotations

import os
from typing import Optional

import httpx


DEFAULT_CONCIERGE_URL = "http://127.0.0.1:8000"
# Sized for Concierge service cold-start tax on first recommend call
# (sentence-transformers load + ChromaDB first-query + Anthropic
# API call at effort=xhigh). See module docstring §Timeout sizing.
DEFAULT_TIMEOUT_SECONDS = 90.0

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
