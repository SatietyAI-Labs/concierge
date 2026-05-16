"""Lifespan pre-warm hook tests — §VIII.2 / D88.

The pre-warm hook fires `MemoryClient.prewarm()` as a background task
at service startup so the ChromaDB + sentence-transformers warmup tax
is paid in a controlled moment rather than on an agent's first
`/recommend` call.

These tests use a fake memory client (`_RecordingMemoryClient`) — they
exercise the lifespan *scheduling and failure-isolation* behavior
without loading the real embedding model, so they stay in the fast
suite (no `integration` marker). The real `prewarm()` is covered by
`tests/test_memory.py::TestPrewarm`.

Patching seam: `core.app` imports `get_settings` and `get_memory_client`
at module scope, so the tests override `core.app.get_settings` /
`core.app.get_memory_client`. Overriding `get_settings` here only
affects the lifespan's `settings` variable — DI-resolved settings
elsewhere are unaffected.
"""
from __future__ import annotations

import asyncio
import logging
import threading

import pytest
from fastapi.testclient import TestClient

from core.app import _prewarm_memory, create_app
from core.config import Settings
from core.memory import MemoryUnavailableError


class _RecordingMemoryClient:
    """Stand-in for `MemoryClient` — records `prewarm()` calls and can
    simulate a backing-store failure. `prewarm_done` lets a test
    thread block deterministically until the background task's worker
    thread has run, regardless of event-loop scheduling.
    """

    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail
        self.prewarm_calls = 0
        self.prewarm_done = threading.Event()

    def prewarm(self) -> None:
        self.prewarm_calls += 1
        try:
            if self._fail:
                raise MemoryUnavailableError("simulated backing-store failure")
        finally:
            self.prewarm_done.set()


def _settings(*, prewarm: bool) -> Settings:
    """A Settings instance with `prewarm_on_startup` pinned. The init
    kwarg outranks the conftest `CONCIERGE_PREWARM_ON_STARTUP=false`
    env var (pydantic-settings init > env priority)."""
    return Settings(prewarm_on_startup=prewarm)


class TestLifespanPrewarmScheduling:
    """The lifespan schedules — or skips — the pre-warm task per the
    `prewarm_on_startup` setting."""

    def test_lifespan_schedules_prewarm_when_enabled(self, monkeypatch):
        fake = _RecordingMemoryClient()
        monkeypatch.setattr("core.app.get_memory_client", lambda: fake)
        monkeypatch.setattr("core.app.get_settings", lambda: _settings(prewarm=True))

        app = create_app()
        with TestClient(app) as tc:
            # The background task runs on the portal loop; block until
            # its worker thread has executed prewarm().
            assert fake.prewarm_done.wait(timeout=10)
            assert tc.get("/health").status_code == 200

        assert fake.prewarm_calls == 1
        assert app.state.prewarm_task is not None

    def test_lifespan_skips_prewarm_when_disabled(self, monkeypatch):
        fake = _RecordingMemoryClient()
        monkeypatch.setattr("core.app.get_memory_client", lambda: fake)
        monkeypatch.setattr("core.app.get_settings", lambda: _settings(prewarm=False))

        app = create_app()
        with TestClient(app) as tc:
            assert tc.get("/health").status_code == 200

        assert app.state.prewarm_task is None
        assert fake.prewarm_calls == 0


class TestLifespanPrewarmFailureIsolation:
    """A failing pre-warm must never crash service startup — the
    `/recommend` path has its own graceful degradation for the same
    `MemoryUnavailableError`."""

    def test_prewarm_task_swallows_memory_unavailable(self, monkeypatch, caplog):
        """The `_prewarm_memory` coroutine catches MemoryUnavailableError
        and logs a WARN — awaiting it directly raises nothing."""
        fake = _RecordingMemoryClient(fail=True)
        monkeypatch.setattr("core.app.get_memory_client", lambda: fake)

        caplog.set_level(logging.WARNING)
        asyncio.run(_prewarm_memory())  # must not raise

        assert fake.prewarm_calls == 1
        assert "memory.prewarm.unavailable" in caplog.text

    def test_failed_prewarm_does_not_crash_startup(self, monkeypatch):
        """With pre-warm enabled but the memory store failing, the
        service still starts cleanly, `/health` returns 200, and the
        lifespan exits without error."""
        fake = _RecordingMemoryClient(fail=True)
        monkeypatch.setattr("core.app.get_memory_client", lambda: fake)
        monkeypatch.setattr("core.app.get_settings", lambda: _settings(prewarm=True))

        app = create_app()
        with TestClient(app) as tc:
            assert fake.prewarm_done.wait(timeout=10)
            assert tc.get("/health").status_code == 200

        assert fake.prewarm_calls == 1
