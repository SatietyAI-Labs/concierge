"""Tests for core.events.EventBroker — in-process SSE fan-out.

Fix Day 4 Task 4. Covers:

- Single-subscriber publish/subscribe round-trip
- Multi-subscriber fan-out
- Graceful subscriber removal on generator cancellation
- Sync `publish` call from a sync context
- `subscriber_count` introspection
- Silent `publish` with zero subscribers

**Cleanup pattern:** async generators don't run their `finally`
blocks on `break` until the generator is aclose()d or GC runs.
Tests use `contextlib.aclosing()` to guarantee deterministic
cleanup timing; the real SSE endpoint achieves the same via
`EventSourceResponse`'s explicit close-on-disconnect path.
"""
from __future__ import annotations

import asyncio
from contextlib import aclosing

import pytest

from core.events import EventBroker


class TestSingleSubscriber:
    @pytest.mark.asyncio
    async def test_publish_delivers_to_subscriber(self):
        broker = EventBroker()

        received: list[dict] = []

        async def consumer():
            async with aclosing(broker.subscribe()) as gen:
                async for event in gen:
                    received.append(event)
                    if len(received) == 1:
                        break

        task = asyncio.create_task(consumer())
        # Give the consumer a tick to register its queue.
        await asyncio.sleep(0)
        broker.publish({"event": "new_request", "data": {"filename": "x.md"}})
        await asyncio.wait_for(task, timeout=1.0)

        assert received == [
            {"event": "new_request", "data": {"filename": "x.md"}}
        ]

    @pytest.mark.asyncio
    async def test_subscriber_count_tracks_active_subscribers(self):
        broker = EventBroker()
        assert broker.subscriber_count() == 0

        async def consumer():
            async with aclosing(broker.subscribe()) as gen:
                async for _event in gen:
                    break

        task = asyncio.create_task(consumer())
        await asyncio.sleep(0)
        assert broker.subscriber_count() == 1

        broker.publish({"event": "x", "data": {}})
        await asyncio.wait_for(task, timeout=1.0)
        # After aclosing() unwinds, the finally clause removes the queue.
        assert broker.subscriber_count() == 0


class TestMultiSubscriber:
    @pytest.mark.asyncio
    async def test_publish_fans_out_to_all_subscribers(self):
        broker = EventBroker()

        received_a: list[dict] = []
        received_b: list[dict] = []

        async def consumer(sink: list[dict]):
            async with aclosing(broker.subscribe()) as gen:
                async for event in gen:
                    sink.append(event)
                    if len(sink) == 1:
                        break

        task_a = asyncio.create_task(consumer(received_a))
        task_b = asyncio.create_task(consumer(received_b))
        await asyncio.sleep(0)

        broker.publish({"event": "new_request", "data": {"n": 1}})
        await asyncio.wait_for(
            asyncio.gather(task_a, task_b), timeout=1.0
        )

        assert received_a == [{"event": "new_request", "data": {"n": 1}}]
        assert received_b == [{"event": "new_request", "data": {"n": 1}}]

    @pytest.mark.asyncio
    async def test_disconnecting_one_subscriber_does_not_affect_others(self):
        broker = EventBroker()
        received_b: list[dict] = []

        async def consumer_a():
            async with aclosing(broker.subscribe()) as gen:
                async for _event in gen:
                    break  # disconnect after one

        async def consumer_b():
            count = 0
            async with aclosing(broker.subscribe()) as gen:
                async for event in gen:
                    received_b.append(event)
                    count += 1
                    if count == 2:
                        break

        task_a = asyncio.create_task(consumer_a())
        task_b = asyncio.create_task(consumer_b())
        await asyncio.sleep(0)

        broker.publish({"event": "x", "data": {"n": 1}})
        await asyncio.wait_for(task_a, timeout=1.0)
        # After a disconnects, only b is subscribed.
        assert broker.subscriber_count() == 1
        broker.publish({"event": "x", "data": {"n": 2}})
        await asyncio.wait_for(task_b, timeout=1.0)

        assert received_b == [
            {"event": "x", "data": {"n": 1}},
            {"event": "x", "data": {"n": 2}},
        ]


class TestZeroSubscribers:
    def test_publish_with_no_subscribers_is_silent(self, caplog):
        """A synchronous publish with zero active subscribers must
        not raise or block. This is the shape service-layer code
        relies on when the FastAPI event loop has no connected UI.
        """
        broker = EventBroker()
        # Must not raise.
        broker.publish({"event": "x", "data": {}})

    def test_subscriber_count_zero_initially(self):
        broker = EventBroker()
        assert broker.subscriber_count() == 0


class TestSyncPublish:
    @pytest.mark.asyncio
    async def test_publish_is_callable_from_sync_context(self):
        """Fix Day 4 Task 4: `create_request` is a sync method;
        `publish` must be sync-callable without blocking or requiring
        the caller to await. The broker's queues are asyncio.Queues
        but put_nowait is non-coroutine-safe as a sync call.
        """
        broker = EventBroker()
        received: list[dict] = []

        async def consumer():
            async with aclosing(broker.subscribe()) as gen:
                async for event in gen:
                    received.append(event)
                    break

        task = asyncio.create_task(consumer())
        await asyncio.sleep(0)

        # Call publish as a plain function — no await.
        broker.publish({"event": "x", "data": {"payload": "from sync"}})
        await asyncio.wait_for(task, timeout=1.0)

        assert received[0]["data"]["payload"] == "from sync"
