"""Integration tests for GET /ui/events and the SSE wire-through.

Fix Day 4 Task 4 + Fix Day 5 Task 1. Strategy:

- **Broker internals** are covered in `tests/test_events.py` (7
  tests, incl. fan-out, disconnect cleanup, sync publish).

- **Service-layer publish** is covered here in `TestServiceWiring`:
  calling `LifecycleService.create_request` with a broker wired in
  produces a `new_request` event visible to a direct subscriber.
  This is the wire-through between service publish and the broker
  that the endpoint reads from.

- **Endpoint registration + routing** is covered here in
  `TestEndpointRegistered`.

- **Full HTTP wire-format byte-identity** lives in
  `TestStreamingWireFormat` (Fix Day 5 Task 1). The test runs a
  real uvicorn server in a background thread on a free localhost
  port — the only reliable transport for SSE in pytest. Every
  in-process alternative tried (TestClient.stream + sync iter_lines
  on Day 4; httpx.AsyncClient + ASGITransport on Day 4 and again
  on Day 5 with pytest-timeout) hangs because httpx's ASGITransport
  awaits the app's `__call__` to fully complete before returning a
  response, which never happens for an infinite EventSourceResponse
  stream. Real HTTP is the ASGI-LIFESPAN-aware harness path that
  today.md / SESSION-2026-04-25-03 Open Question 3 explicitly
  acknowledged as the alternative.

The split keeps every layer covered — broker, service publish,
endpoint registration, payload shape, AND the actual bytes on the
wire — without papering over the protocol behavior.
"""
from __future__ import annotations

import asyncio
import json
import re
import socket
import threading
import time
from contextlib import aclosing
from pathlib import Path

import httpx
import pytest

from core.app import create_app
from core.events import EventBroker


@pytest.fixture
def lifecycle_root(tmp_path) -> Path:
    """Mirror of the fixture in `test_lifecycle_service.py` — three
    lifecycle folders under a tmp_path. Kept local so this file
    doesn't depend on a conftest relocation.
    """
    for folder in ("pending", "resolved", "archived"):
        (tmp_path / folder).mkdir()
    return tmp_path


def _app_with_broker() -> tuple:
    """Build a FastAPI app and attach a fresh EventBroker to app.state
    without running lifespan. Returns (app, broker) so the test can
    publish via the same broker the endpoint would read from.
    """
    app = create_app()
    broker = EventBroker()
    app.state.event_broker = broker
    return app, broker


class TestEndpointRegistered:
    def test_route_is_registered_on_app(self):
        """`/ui/events` must exist on the app. Catches accidental
        router-removal regressions without touching streaming.
        """
        app, _broker = _app_with_broker()
        paths = {route.path for route in app.routes}
        assert "/ui/events" in paths


class TestServiceWiring:
    """Fix Day 4 Fork D: service-layer publish. `LifecycleService
    .create_request` with a broker wired in emits the `new_request`
    event visible to any subscriber on the same broker.
    """

    @pytest.mark.asyncio
    async def test_create_request_publishes_new_request_event(
        self, db_session, lifecycle_root
    ):
        from core.lifecycle_store.schema import NewRequestDraft
        from core.lifecycle_store.service import LifecycleService

        broker = EventBroker()
        svc = LifecycleService(
            session=db_session,
            lifecycle_root=lifecycle_root,
            event_broker=broker,
        )

        received: list[dict] = []

        async def consumer():
            async with aclosing(broker.subscribe()) as gen:
                async for event in gen:
                    received.append(event)
                    break

        task = asyncio.create_task(consumer())
        await asyncio.sleep(0)  # yield so subscribe() registers

        detail = svc.create_request(
            NewRequestDraft(
                tool_name="csvkit-test",
                install_method="pip-user",
                task_context="unit test",
            )
        )

        await asyncio.wait_for(task, timeout=2.0)

        assert len(received) == 1
        event = received[0]
        assert event["event"] == "new_request"
        assert event["data"]["filename"] == detail.filename
        assert event["data"]["tool_name"] == "csvkit-test"
        assert "is_discovered" in event["data"]

    @pytest.mark.asyncio
    async def test_create_request_event_contains_identifying_fields(
        self, db_session, lifecycle_root
    ):
        """The event payload is the shape the UI will consume. Pin
        the field set explicitly: filename, tool_name, tool_slug,
        category, confidence, is_discovered. Missing-field drift here
        would silently break UI rendering.
        """
        from core.lifecycle_store.schema import NewRequestDraft
        from core.lifecycle_store.service import LifecycleService

        broker = EventBroker()
        svc = LifecycleService(
            session=db_session,
            lifecycle_root=lifecycle_root,
            event_broker=broker,
        )

        received: list[dict] = []

        async def consumer():
            async with aclosing(broker.subscribe()) as gen:
                async for event in gen:
                    received.append(event)
                    break

        task = asyncio.create_task(consumer())
        await asyncio.sleep(0)

        svc.create_request(
            NewRequestDraft(
                tool_name="field-check",
                install_method="pip-user",
                task_context="pin field shape",
                confidence="high",
                category="data-processing",
            )
        )

        await asyncio.wait_for(task, timeout=2.0)

        data = received[0]["data"]
        assert set(data.keys()) == {
            "filename",
            "tool_name",
            "tool_slug",
            "category",
            "confidence",
            "is_discovered",
        }

    @pytest.mark.asyncio
    async def test_create_request_without_broker_does_not_raise(
        self, db_session, lifecycle_root
    ):
        """Legacy callers that construct LifecycleService without a
        broker (existing tests, future non-HTTP entrypoints) stay
        functional — the publish path is a conditional no-op.
        """
        from core.lifecycle_store.schema import NewRequestDraft
        from core.lifecycle_store.service import LifecycleService

        svc = LifecycleService(
            session=db_session,
            lifecycle_root=lifecycle_root,
            event_broker=None,
        )
        detail = svc.create_request(
            NewRequestDraft(tool_name="no-broker-test", install_method="pip-user")
        )
        assert detail.filename.endswith("no-broker-test.md")


# ---- Full HTTP wire-format byte-identity (Fix Day 5 Task 1) -------------


def _free_port() -> int:
    """Bind a transient socket to ask the OS for a free port, then
    release. Race window between release and the test's bind is
    negligible for a single-test fixture; if the OS hands the same
    port to another process before uvicorn binds, the test fails
    fast with a clear error rather than hanging.
    """
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def live_uvicorn_server(tmp_path, monkeypatch):
    """Run a real uvicorn server in a background thread on a free
    localhost port. The only transport that reliably supports SSE
    in pytest — every in-process ASGI shim hangs on infinite
    streams (httpx.ASGITransport awaits the app to fully complete;
    sse-starlette never does).

    Settings are env-overridden to point catalog DB / lifecycle
    folders at `tmp_path` so the server's lifespan (Alembic
    upgrade, lifecycle reconcile, APScheduler) operates on
    test-scoped state and never touches the production
    `concierge.db` or `~/.concierge-lifecycle/`.

    Yields the base URL (e.g. `"http://127.0.0.1:54123"`); on
    teardown signals `server.should_exit = True` and joins the
    thread with a 5s ceiling.
    """
    import uvicorn

    db_path = tmp_path / "concierge-test.db"
    lifecycle_root = tmp_path / "lifecycle"
    for sub in ("pending", "resolved", "archived"):
        (lifecycle_root / sub).mkdir(parents=True)
    memory_dir = tmp_path / "memory"  # not exercised here but isolated

    monkeypatch.setenv("CONCIERGE_DATABASE_PATH", str(db_path))
    monkeypatch.setenv("CONCIERGE_LIFECYCLE_ROOT", str(lifecycle_root))
    monkeypatch.setenv("CONCIERGE_MEMORY_DIR", str(memory_dir))
    monkeypatch.setenv("CONCIERGE_LOG_LEVEL", "ERROR")

    # `get_settings` + `get_engine` + `get_session_factory` are all
    # `@lru_cache`d at module level. Earlier tests in this run may
    # have populated those caches against the prior env. Clear them
    # so the new env vars apply to this server's lifespan.
    from core.app import create_app as create_core_app
    from core.config import get_settings
    from core.db.session import get_engine, get_session_factory

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    config = uvicorn.Config(
        create_core_app,
        factory=True,
        host="127.0.0.1",
        port=port,
        log_level="error",
        access_log=False,
        # Force loop=asyncio so test thread doesn't conflict with
        # the runtime venv's potential uvloop install.
        loop="asyncio",
    )
    server = uvicorn.Server(config)

    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    # Poll /health until the server is up. Lifespan runs alembic +
    # lifecycle reconcile + APScheduler.start; ~1-2s on a warm
    # cache, longer on first-ever alembic import.
    deadline = time.monotonic() + 20.0
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{base_url}/health", timeout=0.5)
            if r.status_code == 200:
                break
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ReadError):
            pass
        time.sleep(0.1)
    else:
        server.should_exit = True
        server_thread.join(timeout=2.0)
        pytest.fail(
            f"uvicorn server at {base_url} did not become ready within 20s"
        )

    yield base_url

    # Teardown — graceful exit; daemon=True is the backstop if the
    # process tries to leave with the thread still alive.
    server.should_exit = True
    server_thread.join(timeout=5.0)
    # Clear caches so subsequent tests don't pick up the test env.
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


class TestStreamingWireFormat:
    """Drive `/ui/events` over a real uvicorn server, trigger a
    `POST /requests`, and assert the bytes on the wire match the
    SSE event format. Closes the deferred coverage from Fix Day 4
    Task 4 and the broker-direct + manual-curl gap flagged in
    `SESSION-2026-04-25-03.md` Open Question 3.

    Why a real server instead of an in-process ASGI shim:
    `httpx.ASGITransport.handle_async_request` awaits
    `self.app(scope, receive, send)` to *completely* return before
    yielding the response. EventSourceResponse never returns —
    it's an infinite stream by design — so any in-process variant
    hangs on the first stream open. Confirmed empirically Day 4
    (httpx + ASGITransport hung) and re-confirmed Day 5 with
    pytest-timeout in place. The real-uvicorn fixture is the
    "ASGI-LIFESPAN-aware harness" path that today.md acknowledged
    as the alternative.

    Cancellation discipline: the consumer breaks out of `async for
    aiter_bytes()` once the `event: new_request\\ndata: {...}\\n\\n`
    block is assembled; the `async with client.stream(...)` exit
    closes the connection at the TCP level; the server-side
    generator observes the disconnect via Starlette's request
    cycle and unwinds. `asyncio.wait_for` inside + `pytest.mark
    .timeout` outside guard against a stuck read.
    """

    @pytest.mark.timeout(45, method="thread")
    @pytest.mark.asyncio
    async def test_new_request_event_appears_on_wire_with_correct_format(
        self, live_uvicorn_server
    ):
        base_url = live_uvicorn_server

        async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
            stream_chunks: list[bytes] = []

            async def reader() -> None:
                async with client.stream("GET", "/ui/events") as response:
                    assert response.status_code == 200, (
                        f"GET /ui/events status={response.status_code}: "
                        f"{await response.aread()!r}"
                    )
                    # Pin content-type so a future regression that
                    # silently demotes the response (e.g. JSONResponse)
                    # surfaces as a clear failure rather than as a
                    # parse error in the regex below.
                    assert response.headers["content-type"].startswith(
                        "text/event-stream"
                    ), response.headers
                    async for chunk in response.aiter_bytes():
                        stream_chunks.append(chunk)
                        accumulated = b"".join(stream_chunks)
                        # sse-starlette emits pings as comment lines
                        # (`: ping ...`) which contain a blank-line
                        # terminator but NO `event:` line — so the
                        # break requires both the event-name marker
                        # AND a blank-line terminator after it.
                        # sse-starlette uses CRLF line endings
                        # (`\r\n\r\n`) by default but the SSE spec
                        # also permits LF-only (`\n\n`); accept both.
                        if b"event: new_request" in accumulated:
                            suffix = accumulated.split(
                                b"event: new_request", 1
                            )[1]
                            if b"\r\n\r\n" in suffix or b"\n\n" in suffix:
                                break

            async def publisher() -> dict:
                # Small delay to let the SSE handler subscribe in the
                # server before we publish. Real-HTTP path: no
                # in-process broker introspection from the test side,
                # so a fixed delay replaces the broker-count poll
                # used in the broker-direct tests.
                await asyncio.sleep(0.5)
                resp = await client.post(
                    "/requests",
                    json={
                        "tool_name": "streaming-wire-test",
                        "install_method": "pip-user",
                        "task_context": (
                            "Fix Day 5 Task 1 — wire-format byte test"
                        ),
                    },
                )
                assert resp.status_code == 201, (
                    f"POST /requests status={resp.status_code}: {resp.text}"
                )
                return resp.json()

            reader_task = asyncio.create_task(reader())
            try:
                detail = await publisher()
                await asyncio.wait_for(reader_task, timeout=10.0)
            except Exception:
                reader_task.cancel()
                raise

        # Now assert the wire format on the accumulated bytes.
        wire = b"".join(stream_chunks).decode("utf-8")

        # `event: <name>\n` followed by `data: <json>\n\n`. Line
        # endings may be `\n` or `\r\n` depending on sse-starlette
        # version — the regex is permissive on the terminator.
        match = re.search(
            r"event:\s*new_request\r?\ndata:\s*(?P<json>\{.+?\})\r?\n",
            wire,
        )
        assert match is not None, (
            "Did not find `event: new_request` followed by `data: {...}` "
            f"in stream bytes. Accumulated wire content:\n{wire!r}"
        )

        raw_data = match.group("json")

        # Pin: the data field must be JSON, not Python repr. The
        # original bug (Fix Day 5 Task 1 discovery) emitted
        # `data: {'filename': '...', 'category': None}` — single
        # quotes + `None` — which `JSON.parse()` in the browser
        # rejects. A future regression that re-introduces repr-style
        # serialization (e.g. someone "helpfully" wraps data with
        # `str()` somewhere upstream) would parse-fail in HTMX
        # silently. Pinning the JSON-ness explicitly catches that
        # before it ships. `'{` (single-quote-after-brace) is the
        # canonical Python-repr signature; double-quoted JSON cannot
        # contain it as a leading character.
        assert "'" not in raw_data.split('"', 1)[0], (
            "Data field uses single quotes — looks like Python repr, "
            "not JSON. sse-starlette default str()-fallback regression? "
            f"raw_data={raw_data!r}"
        )

        # Now actually parse as JSON. `json.loads` raises
        # `json.JSONDecodeError` on Python repr (single quotes,
        # `None`/`True`/`False` capitalization), so this is the
        # load-bearing wire-contract assertion. Tests that only
        # regex-match the field set without `json.loads` pass on
        # both JSON and JSON-ish-but-actually-Python-repr output —
        # the original bug would have slipped through such a test.
        data = json.loads(raw_data)
        assert isinstance(data, dict), (
            f"Parsed data is not a dict (got {type(data).__name__}): {data!r}"
        )

        # Re-pin the field set Fork D documented (filename,
        # tool_name, tool_slug, category, confidence, is_discovered).
        # The unit-level shape is also pinned in
        # `TestServiceWiring::test_create_request_event_contains_identifying_fields`;
        # this re-pin verifies the field set survives the SSE
        # serialization round-trip and round-trips through json.loads.
        assert data["filename"] == detail["filename"]
        assert data["tool_name"] == "streaming-wire-test"
        assert set(data.keys()) == {
            "filename",
            "tool_name",
            "tool_slug",
            "category",
            "confidence",
            "is_discovered",
        }
        # JSON null (the wire form) round-trips to Python `None`
        # via json.loads — pin so a regression that shipped
        # `data: ... 'category': None ...` (Python repr of None,
        # which JSON.parse rejects with SyntaxError) gets caught.
        assert data["category"] is None
        assert data["confidence"] is None
        # JSON bool round-trips to Python bool. `is_discovered=False`
        # in the broker dict serializes to JSON `false`; if Python
        # repr leaked through it'd be `False`, which json.loads
        # would reject above. Belt-and-suspenders re-assert.
        assert data["is_discovered"] is False
