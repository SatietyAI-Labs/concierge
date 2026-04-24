"""Integration tests for the scanner's HTTP surface.

Fix Day 4 Task 5:

- `POST /scanner/run` — manual trigger returning the summary
- `GET /health` `scanner` field — populated after a run, null
  before any run

The APScheduler weekly job cadence is NOT tested here — weekly
means the job fires once a week, which isn't useful to drive from
a unit harness. The manual trigger endpoint exercises the same
underlying `run_once` code path that the scheduler calls.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from core.app import create_app
from core.db.models import Tool, ToolUsageEvent
from core.db.session import get_db


NOW = datetime.now(timezone.utc)


@pytest.fixture
def client_with_scanner(db_session):
    """TestClient with DB overridden to the fixture session. Used
    for both the scanner-trigger and health-integration tests.
    """
    app = create_app()
    app.dependency_overrides[get_db] = lambda: (yield db_session)
    # Scanner endpoint reads app.state.memory (optional) and
    # writes app.state.last_scanner_summary. Lifespan hasn't run
    # here (TestClient is not a context manager), so we initialize
    # the summary slot to None.
    app.state.last_scanner_summary = None
    with TestClient(app) as tc:
        yield tc, app


class TestScannerRunEndpoint:
    def test_empty_db_returns_no_candidates(self, client_with_scanner):
        client, _app = client_with_scanner
        resp = client.post("/scanner/run")
        assert resp.status_code == 200
        body = resp.json()
        assert body["auto_promoted_count"] == 0
        assert body["promotion_candidates_count"] == 0
        assert body["demotion_candidates_count"] == 0
        assert body["stale_pending_count"] == 0
        assert body["errors"] == []

    def test_run_auto_promotes_when_signal_is_unambiguous(
        self, client_with_scanner, db_session
    ):
        client, _app = client_with_scanner

        tool = Tool(
            slug="promoteable",
            name="promoteable",
            tool_type="cli",
            lifecycle_state="used",
            created_at=NOW - timedelta(days=60),
        )
        db_session.add(tool)
        db_session.flush()
        for _ in range(5):
            db_session.add(
                ToolUsageEvent(
                    tool_id=tool.id,
                    event_type="recommended",
                    timestamp=NOW - timedelta(days=3),
                )
            )
        db_session.commit()

        resp = client.post("/scanner/run")
        assert resp.status_code == 200
        body = resp.json()
        assert body["auto_promoted_count"] == 1
        assert "promoteable" in body["auto_promoted_slugs"]

        db_session.refresh(tool)
        assert tool.lifecycle_state == "loaded-on-boot"

    def test_run_summary_stored_on_app_state(self, client_with_scanner):
        client, app = client_with_scanner
        # Pre-condition: no summary yet.
        assert app.state.last_scanner_summary is None
        client.post("/scanner/run")
        # Post-condition: a summary lives on app.state.
        assert app.state.last_scanner_summary is not None
        assert app.state.last_scanner_summary.ran_at is not None


class TestHealthScannerField:
    def test_health_scanner_field_null_before_any_run(
        self, client_with_scanner
    ):
        """Fresh process → no scan has run → scanner field is null.
        Operator reading /health sees "no data yet" explicitly.
        """
        client, _app = client_with_scanner
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert "scanner" in body
        assert body["scanner"] is None

    def test_health_scanner_field_populated_after_run(
        self, client_with_scanner
    ):
        client, _app = client_with_scanner
        client.post("/scanner/run")
        resp = client.get("/health")
        body = resp.json()
        assert body["scanner"] is not None
        # Shape pins — same field set as ScannerSummary.to_health_dict.
        assert "last_ran_at" in body["scanner"]
        assert "auto_promoted_count" in body["scanner"]
        assert "promotion_candidates_count" in body["scanner"]
        assert "demotion_candidates_count" in body["scanner"]
        assert "stale_pending_count" in body["scanner"]
