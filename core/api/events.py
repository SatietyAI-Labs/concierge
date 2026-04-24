"""SSE endpoint for UI real-time updates.

Fix Day 4 Task 4 — C3 dual-channel real-time surface. `GET /ui/events`
streams `new_request` events (and future event types) to connected
UI clients. Service-layer publishers (`LifecycleService.create_request`)
fan out via the per-app `EventBroker`; each connected client gets
its own subscriber queue on the FastAPI event loop.

## HTMX-friendly format

Each event is emitted as:

    event: new_request
    data: {"filename": "...", "tool_name": "...", ...}

HTMX's `hx-sse` extension pairs `sse-swap="new_request"` /
`hx-trigger="sse:new_request from:body"` with this event-name
convention. No special client-side parsing needed beyond the
built-in.

## Keep-alive / ping

`sse-starlette`'s `EventSourceResponse` sends periodic pings by
default (every 15s) to keep the connection alive through proxies.
We rely on the default — no explicit ping logic.

## Disconnect handling

When a client disconnects, the subscriber async generator hits
`GeneratorExit` and the `finally` block in `EventBroker.subscribe`
removes the queue. The endpoint does not need explicit cleanup.
"""
from __future__ import annotations

import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from core.events import EventBroker


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ui", tags=["ui"])


def get_event_broker_from_request(request: Request) -> EventBroker:
    """Resolve the per-app broker. Wired in `core/app.py` lifespan.

    Duplicate of `core.api.requests.get_event_broker` — kept local
    so the events router doesn't import from the requests router,
    which would couple two otherwise-independent surfaces.
    """
    return request.app.state.event_broker


@router.get("/events")
async def events(broker: EventBroker = Depends(get_event_broker_from_request)):
    """SSE stream of UI events. Currently emits `new_request` when a
    pending tool-request is filed; future event types (scanner runs,
    install completions, etc.) will layer on without a second
    endpoint.

    The stream runs until the client disconnects. No pagination, no
    replay — SSE is push-only; clients that reconnect after a drop
    receive only new events, not historical ones. A future
    enhancement (deferred) is Last-Event-ID replay from a bounded
    ring buffer.
    """

    async def _stream() -> AsyncIterator[dict]:
        logger.debug("ui.events.client_connected")
        async for event in broker.subscribe():
            yield event
        logger.debug("ui.events.client_disconnected")

    return EventSourceResponse(_stream())
