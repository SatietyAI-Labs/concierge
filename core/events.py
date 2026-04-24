"""In-process event broker for SSE fan-out.

Fix Day 4 Task 4 — C3 dual-channel real-time surface. Service-layer
publish, endpoint-layer stream. One `EventBroker` instance per
FastAPI application; each SSE subscriber gets its own
`asyncio.Queue` on the app's event loop. Publishers call `publish`
synchronously (no `await` needed) so sync service methods can emit
without becoming async.

## Design notes

- **Unbounded queues.** Expected subscribers = one browser tab open
  on the operator UI. Event rate = one `new_request` per operator
  action, at most a few per minute during demo/soak. Bounded queues
  add complexity (choice between drop-old and drop-new) without
  solving a real problem at this scale. Revisit if the UI ever has
  >10 concurrent tabs or bursty publisher patterns.

- **asyncio.Queue, not janus or queue.Queue.** Queue is created on
  the subscriber's event loop in `subscribe()`. `put_nowait` is a
  sync method that does NOT require the loop to be running in the
  calling thread — it appends directly to the deque. This is why
  `publish` can be sync and still safely write to async-queue
  subscribers.

- **Swallow-on-full policy.** Even though queues are unbounded, the
  `QueueFull` exception path is still caught + logged at WARNING.
  A future bounded-queue reconfiguration should not require
  changing publisher call sites.

- **Graceful subscriber removal.** `subscribe()` is an async
  generator; on disconnect, the finally block removes the queue
  from the broker's subscriber list. No polling, no health-check.

## Event shape

Publishers build a dict with at least:
  - `event`: str — the SSE event name (e.g. `"new_request"`)
  - `data`: Any — JSON-serializable payload

Consumers pass through to `sse_starlette.sse.EventSourceResponse`,
which serializes `data` (via `json.dumps` by default) and emits
`event: <name>\ndata: <json>\n\n` on the wire.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Optional


log = logging.getLogger("concierge.events")


class EventBroker:
    """Fan-out broker for SSE events.

    One instance per FastAPI app (created in `lifespan`). Service
    code calls `publish(event)` synchronously; SSE endpoints call
    `subscribe()` and iterate the yielded queue to stream to their
    client.
    """

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue] = []

    # ---- Subscriber interface ---------------------------------------

    async def subscribe(self) -> AsyncIterator[dict[str, Any]]:
        """Register a new subscriber queue and yield events as they
        arrive. On subscriber disconnect (generator cleanup), remove
        the queue from the broker.

        Consumer pattern:

            async for event in broker.subscribe():
                yield event  # or push to SSE stream

        The generator must run on the event loop the queue was
        created on — i.e. the calling request's FastAPI event loop.
        No cross-loop publish is supported.
        """
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(queue)
        log.debug("events.subscribe subscriber_count=%d", len(self._subscribers))
        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            # Remove on client disconnect / generator cancellation.
            try:
                self._subscribers.remove(queue)
            except ValueError:
                pass
            log.debug(
                "events.unsubscribe subscriber_count=%d",
                len(self._subscribers),
            )

    # ---- Publisher interface ----------------------------------------

    def publish(self, event: dict[str, Any]) -> None:
        """Fan an event out to every currently-subscribed queue.

        Synchronous — safe to call from sync service methods. Any
        `asyncio.QueueFull` (impossible with unbounded queues but
        caught in case of future bounded-queue reconfiguration) is
        logged at WARNING; the publish itself never raises so a
        slow / disconnected subscriber cannot break a producer.
        """
        if not self._subscribers:
            log.debug(
                "events.publish_no_subscribers event=%s",
                event.get("event"),
            )
            return
        delivered = 0
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
                delivered += 1
            except asyncio.QueueFull:
                log.warning(
                    "events.publish_queue_full event=%s "
                    "queue_size=%d",
                    event.get("event"),
                    queue.qsize(),
                )
        log.debug(
            "events.publish event=%s delivered=%d/%d",
            event.get("event"),
            delivered,
            len(self._subscribers),
        )

    # ---- Introspection (for tests / /health) ------------------------

    def subscriber_count(self) -> int:
        return len(self._subscribers)


__all__ = ["EventBroker"]
