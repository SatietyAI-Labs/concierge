"""Tests for core/telemetry.py — ToolUsageEvent emit helpers.

Covers the pure-function emit path plus the make_db_sink factory. Fix
Day 3 Fork 2: session_id is uniformly None for all three emit sites
today; the telemetry signature lets callers pass a session_id but
production wiring doesn't populate it yet.
"""
from __future__ import annotations

import logging

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from core.db.base import Base
from core.db import models  # noqa: F401 — register on Base.metadata
from core.db.models import Tool, ToolUsageEvent
from core.telemetry import (
    UsageEventSink,
    emit_usage_event,
    make_db_sink,
    noop_sink,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=True)
    s = factory()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def seeded_tool(session: Session) -> Tool:
    t = Tool(slug="csvkit", name="csvkit", tool_type="cli")
    session.add(t)
    session.commit()
    return t


class TestEmitUsageEvent:
    def test_emit_writes_row(self, session: Session, seeded_tool: Tool):
        evt = emit_usage_event(
            session,
            tool_slug="csvkit",
            event_type="recommended",
            context={"rank": 1},
        )
        assert evt is not None
        session.commit()
        fetched = session.query(ToolUsageEvent).one()
        assert fetched.tool_id == seeded_tool.id
        assert fetched.event_type == "recommended"
        assert fetched.context == {"rank": 1}
        assert fetched.session_id is None

    def test_emit_returns_none_on_missing_slug(
        self, session: Session, caplog: pytest.LogCaptureFixture
    ):
        with caplog.at_level(logging.WARNING, logger="concierge.telemetry"):
            result = emit_usage_event(
                session, tool_slug="ghost", event_type="recommended"
            )
        assert result is None
        assert any("slug_not_found" in r.message for r in caplog.records)
        assert session.query(ToolUsageEvent).count() == 0

    def test_emit_raises_on_unknown_event_type(
        self, session: Session, seeded_tool: Tool
    ):
        with pytest.raises(ValueError, match="unknown event_type"):
            emit_usage_event(
                session, tool_slug="csvkit", event_type="bogus"
            )

    def test_emit_accepts_all_five_event_types(
        self, session: Session, seeded_tool: Tool
    ):
        from core.db.models import USAGE_EVENT_TYPE_VALUES
        for et in USAGE_EVENT_TYPE_VALUES:
            evt = emit_usage_event(
                session, tool_slug="csvkit", event_type=et
            )
            assert evt is not None
        session.commit()
        seen = {
            e.event_type for e in session.query(ToolUsageEvent).all()
        }
        assert seen == set(USAGE_EVENT_TYPE_VALUES)

    def test_emit_context_is_nullable(
        self, session: Session, seeded_tool: Tool
    ):
        evt = emit_usage_event(
            session, tool_slug="csvkit", event_type="loaded"
        )
        assert evt is not None
        assert evt.context is None


class TestSinkFactories:
    def test_noop_sink_accepts_and_returns_none(self):
        assert noop_sink("x", "recommended", None) is None
        assert noop_sink("x", "recommended", {"rank": 1}) is None

    def test_make_db_sink_writes_through(
        self, session: Session, seeded_tool: Tool
    ):
        sink: UsageEventSink = make_db_sink(session)
        sink("csvkit", "recommended", {"rank": 1, "request_id": "abc"})
        session.commit()
        fetched = session.query(ToolUsageEvent).one()
        assert fetched.event_type == "recommended"
        assert fetched.context["rank"] == 1

    def test_make_db_sink_missing_slug_warns_no_raise(
        self, session: Session, caplog: pytest.LogCaptureFixture
    ):
        sink = make_db_sink(session)
        with caplog.at_level(logging.WARNING, logger="concierge.telemetry"):
            sink("ghost", "recommended", None)  # must not raise
        assert any("slug_not_found" in r.message for r in caplog.records)
        assert session.query(ToolUsageEvent).count() == 0
