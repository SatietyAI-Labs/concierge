"""Integration tests for `POST /recommend` telemetry persistence.

The wiring-test gap that hid the Fix Day 5 telemetry-commit bug is
this: every existing recommend test substitutes the sink (with
`_CapturingSink`) or substitutes the service (with `_StubService`).
None exercises the **full request → committed-row chain**:

    real endpoint → real RecommendationService → real make_db_sink
    → real Session lifecycle (open per request, close in finally)
    → fresh-session SELECT against the same engine post-request

That is the chain the production failure lives in. The bug rolled
back the implicit transaction at session close because the endpoint
never called `db.commit()`. Without a fresh-session post-request
read, autoflush masks the rollback (the row sits in the request
session's identity map until it's closed).

These tests pin the chain end-to-end. They use:

  - a shared in-memory SQLite engine (so multiple sessions see the
    same committed state)
  - an override of `get_db` that **mimics production** — opens a
    new session per request and closes in `finally`. Without the
    close, the bug is invisible.
  - a real `RecommendationService` (not stubbed) so the real
    `make_db_sink(db)` runs against the real session
  - a stubbed `AnthropicRecommender` returning canned parseable
    JSON content with controlled in-catalog / discovery mix
  - a stubbed `MemoryClient` (search → [], identity_get → "") so
    no ChromaDB boot
  - a **fresh verification session** opened after the request so
    the read sees only committed state

Two variants:

  1. Two in-catalog recs → expect exactly 2 `recommended` rows.
     Pins per-rec emit (not single-emit-regardless-of-count).
  2. One in-catalog + one discovery rec → expect exactly 1 row.
     Pins the discovery-skip behavior so a future "always emit"
     regression doesn't sneak past.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from core.api.recommend import get_anthropic_recommender
from core.app import create_app
from core.db.base import Base
from core.db import models  # noqa: F401 — register models on Base.metadata
from core.db.models import Tool, ToolUsageEvent
from core.db.session import get_db
from core.memory import MemoryClient, get_memory_client
from core.recommend.client import AnthropicCall


# ---- Stubs ---------------------------------------------------------------


@dataclass
class _StubAnthropic:
    """Substitute for `AnthropicRecommender`. Returns canned content
    on `.call(system=..., user=...)`. The service's real parser runs
    against this content so the JSON shape must round-trip through
    `parse_recommendation_response`.

    `effort` is read by the service for the per-request INFO log
    summary; `model` is also referenced in some code paths. Both
    are echoed verbatim into the response.
    """

    content: str
    model: str = "claude-opus-4-7"
    effort: str = "xhigh"

    def call(self, *, system: str, user: str) -> AnthropicCall:
        return AnthropicCall(
            content=self.content,
            stop_reason="end_turn",
            tokens_in=100,
            tokens_out=50,
            model_echo="claude-opus-4-7",
            latency_ms=10,
        )


class _StubMemory:
    """Substitute for `MemoryClient`. No ChromaDB boot. `.search`
    returns []; `.identity_get` returns ""; mirrors the FakeMemory
    pattern from test_integration_full_cycle.
    """

    def search(self, query, *, tag_filter=None, importance_filter=None, limit=10):
        return []

    def identity_get(self, *, key: str = "primary") -> str:
        return ""

    def identity_set(self, text: str, *, key: str = "primary") -> None:
        pass


# ---- Fixtures ------------------------------------------------------------


@pytest.fixture
def shared_engine() -> Iterator[Engine]:
    """In-memory SQLite shared across sessions (StaticPool keeps the
    one connection alive so multiple sessions see the same DB).
    Tables created once; dropped on teardown.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)


@pytest.fixture
def session_factory(shared_engine) -> sessionmaker[Session]:
    return sessionmaker(bind=shared_engine, autocommit=False, autoflush=True)


@pytest.fixture
def seeded_catalog(session_factory) -> None:
    """Seed two in-catalog tools (`csvstat`, `xsv`) so the
    recommendations pointing at those slugs cause `emit_usage_event`
    to find a Tool row. Commits via a separate session so the writes
    are persistent against the shared engine before the request runs.
    """
    with session_factory() as seed:
        seed.add(
            Tool(
                slug="csvstat",
                name="csvstat",
                description="Lightweight CSV stats CLI.",
                tool_type="cli",
                category="data-processing",
                install_method="pip-user",
                is_in_manifest=True,
                lifecycle_state="loaded-on-boot",
            )
        )
        seed.add(
            Tool(
                slug="xsv",
                name="xsv",
                description="Fast CSV toolkit in Rust.",
                tool_type="cli",
                category="data-processing",
                install_method="binary",
                is_in_manifest=True,
                lifecycle_state="loaded-on-boot",
            )
        )
        seed.commit()


@pytest.fixture
def client(shared_engine, session_factory, seeded_catalog) -> Iterator[TestClient]:
    """TestClient with the recommend dependency stack wired against
    the shared in-memory engine. `get_db` is overridden to mimic
    production exactly: open a new session per request, close in
    `finally`. The `finally`-close is the load-bearing detail — it's
    what triggers the implicit-transaction rollback when the endpoint
    forgets to commit.

    Bare `TestClient(app)` — NOT used as a context manager — so the
    app lifespan (Alembic upgrade, lifecycle reconcile, APScheduler,
    EventBroker) is skipped. The recommend endpoint depends on none
    of those; the existing recommend-api fixtures take the same
    approach (see `tests/conftest.py::client`).
    """
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_memory_client] = lambda: _StubMemory()
    # Default stub — tests parametrize content via a per-test override.
    app.dependency_overrides[get_anthropic_recommender] = lambda: _StubAnthropic(
        content=_TWO_IN_CATALOG_CONTENT
    )

    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# ---- Canned response payloads -------------------------------------------


_TWO_IN_CATALOG_CONTENT = json.dumps(
    {
        "reasoning": "Both tools handle CSV stats well.",
        "recommendations": [
            {
                "rank": 1,
                "tool_slug": "csvstat",
                "tool_name": "csvstat",
                "rationale": "Lightweight CLI, ships with csvkit.",
                "confidence": "high",
                "is_in_catalog": True,
                "category": "data-processing",
                "install_method": "pip-user",
                "risk_cost": "tiny",
            },
            {
                "rank": 2,
                "tool_slug": "xsv",
                "tool_name": "xsv",
                "rationale": "Faster on large files.",
                "confidence": "medium",
                "is_in_catalog": True,
                "category": "data-processing",
                "install_method": "binary",
                "risk_cost": "small binary",
            },
        ],
    }
)


_ONE_IN_CATALOG_ONE_DISCOVERY_CONTENT = json.dumps(
    {
        "reasoning": "csvstat is in catalog; mlr would be a discovery.",
        "recommendations": [
            {
                "rank": 1,
                "tool_slug": "csvstat",
                "tool_name": "csvstat",
                "rationale": "Lightweight CLI, ships with csvkit.",
                "confidence": "high",
                "is_in_catalog": True,
                "category": "data-processing",
                "install_method": "pip-user",
                "risk_cost": "tiny",
            },
            {
                "rank": 2,
                "tool_slug": None,
                "tool_name": "miller",
                "rationale": "Powerful but not in catalog.",
                "confidence": "medium",
                "is_in_catalog": False,
                "category": "data-processing",
                "install_method": "binary",
                "risk_cost": "small binary",
            },
        ],
    }
)


# ---- Tests ---------------------------------------------------------------


class TestRecommendEndpointPersistsTelemetry:
    """The load-bearing acceptance test for the Fix Day 5 telemetry-
    commit bug. These assertions fail on commit `ab1bf31` (rollback
    wins, count=0) and pass after the endpoint calls `db.commit()`.
    """

    def test_two_in_catalog_recs_persist_two_recommended_events(
        self, client, session_factory
    ):
        # Default fixture content is two-in-catalog. Hit the endpoint
        # exactly once and assert the row count.
        resp = client.post(
            "/recommend",
            json={"task": "compute top 5 rows by revenue from a CSV"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # Sanity-check the response — both recs in-catalog, both
        # eligible to emit. If parsing or the catalog lookup misfires
        # the assertion below would also fail, so guard upfront.
        assert len(body["recommendations"]) == 2
        assert all(r["is_in_catalog"] for r in body["recommendations"])

        # Open a FRESH verification session post-request. Reading
        # from the same session the request used would let autoflush
        # mask the bug. The fresh session sees only committed state.
        with session_factory() as fresh:
            rows = (
                fresh.query(ToolUsageEvent)
                .filter(ToolUsageEvent.event_type == "recommended")
                .all()
            )

        assert len(rows) == 2, (
            f"expected 2 'recommended' rows (one per in-catalog rec), got {len(rows)}. "
            "If 0: the endpoint emitted but never committed and the rollback won "
            "(this is the Fix Day 5 bug). If 1: per-rec emit regressed to single-emit. "
            "If >2: emit fired more than once per rec — a different regression."
        )
        # Pin the slugs match what the stub returned, not arbitrary
        # tools; rules out a coincidental row count match if the
        # service ever started emitting on unrelated tools.
        slugs = {fresh.get(Tool, r.tool_id).slug for r in rows}
        assert slugs == {"csvstat", "xsv"}

    def test_discovery_rec_does_not_emit_event(
        self, shared_engine, session_factory, seeded_catalog
    ):
        # Override the default two-in-catalog stub with the
        # one-in-catalog + one-discovery variant. The discovery rec
        # has tool_slug=None and the service `continue`s on it; only
        # the in-catalog rec should produce a row.
        app = create_app()

        def override_get_db() -> Iterator[Session]:
            s = session_factory()
            try:
                yield s
            finally:
                s.close()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_memory_client] = lambda: _StubMemory()
        app.dependency_overrides[get_anthropic_recommender] = lambda: _StubAnthropic(
            content=_ONE_IN_CATALOG_ONE_DISCOVERY_CONTENT
        )

        try:
            tc = TestClient(app)
            resp = tc.post(
                "/recommend",
                json={"task": "row-by-row CSV transformations"},
            )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body["recommendations"]) == 2
        assert [r["is_in_catalog"] for r in body["recommendations"]] == [True, False]

        with session_factory() as fresh:
            rows = (
                fresh.query(ToolUsageEvent)
                .filter(ToolUsageEvent.event_type == "recommended")
                .all()
            )

        assert len(rows) == 1, (
            f"expected exactly 1 'recommended' row (in-catalog only; discovery skipped), "
            f"got {len(rows)}. If 2: a regression made discovery recs emit too. "
            "If 0: the telemetry-commit fix regressed."
        )
        only = fresh.get(Tool, rows[0].tool_id)
        assert only.slug == "csvstat"
