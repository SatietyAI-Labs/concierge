"""Wiring tests for GET /stats/top-tools — Day 10 Task 1.

Contracts under test:

1. **Empty DB** returns 200 + empty items list (designed empty state at
   API layer; UI handles empty rendering separately).
2. **Result orders by `times_recommended` DESC.**
3. **Limited to top 3** even when more tools have recommendations.
4. **Filter respects `event_type='recommended'`** — events of other
   types (`installed`/`loaded`/`used`/`removed`) do not contribute to
   the count.
5. **Response shape:** each entry has `slug`, `name`, `times_recommended`.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from core.app import create_app
from core.db.models import Tool, ToolUsageEvent
from core.db.session import get_db


def _client_with_session(db_session) -> TestClient:
    """Build a fresh TestClient wired to the supplied db_session via
    dependency override. Per-test fresh app isolates dependency
    overrides — no cross-test contamination.
    """
    app = create_app()
    app.dependency_overrides[get_db] = lambda: (yield db_session)
    return TestClient(app)


class TestStatsTopToolsContract:

    def test_empty_db_returns_empty_items_list(self, db_session):
        client = _client_with_session(db_session)
        resp = client.get("/stats/top-tools")
        assert resp.status_code == 200
        assert resp.json() == {"items": []}

    def test_orders_by_times_recommended_desc(self, db_session):
        # ripgrep × 5, fd × 3, jq × 1 — distinct counts so ordering
        # is deterministic.
        ripgrep = Tool(slug="ripgrep", name="ripgrep", is_in_manifest=True)
        fd = Tool(slug="fd", name="fd", is_in_manifest=True)
        jq = Tool(slug="jq", name="jq", is_in_manifest=True)
        db_session.add_all([ripgrep, fd, jq])
        db_session.flush()
        for _ in range(5):
            db_session.add(
                ToolUsageEvent(tool_id=ripgrep.id, event_type="recommended")
            )
        for _ in range(3):
            db_session.add(
                ToolUsageEvent(tool_id=fd.id, event_type="recommended")
            )
        db_session.add(ToolUsageEvent(tool_id=jq.id, event_type="recommended"))
        db_session.commit()

        client = _client_with_session(db_session)
        items = client.get("/stats/top-tools").json()["items"]
        assert [(it["slug"], it["times_recommended"]) for it in items] == [
            ("ripgrep", 5),
            ("fd", 3),
            ("jq", 1),
        ]

    def test_top_3_truncates_when_more_tools_have_recommendations(
        self, db_session
    ):
        tools = [
            Tool(slug=f"tool-{i}", name=f"tool-{i}", is_in_manifest=True)
            for i in range(5)
        ]
        db_session.add_all(tools)
        db_session.flush()
        # Distinct counts so ordering is unambiguous: 10 > 7 > 5 > 3 > 1
        counts = [10, 7, 5, 3, 1]
        for tool, n in zip(tools, counts):
            for _ in range(n):
                db_session.add(
                    ToolUsageEvent(tool_id=tool.id, event_type="recommended")
                )
        db_session.commit()

        client = _client_with_session(db_session)
        items = client.get("/stats/top-tools").json()["items"]
        assert len(items) == 3
        assert [it["times_recommended"] for it in items] == [10, 7, 5]

    def test_only_recommended_events_count(self, db_session):
        # Tool with all OTHER event types but no recommended events
        # → must NOT appear in result. Tool with recommended events
        # → must appear.
        only_other = Tool(
            slug="only-other", name="only-other", is_in_manifest=True
        )
        with_rec = Tool(slug="with-rec", name="with-rec", is_in_manifest=True)
        db_session.add_all([only_other, with_rec])
        db_session.flush()
        for et in ("installed", "loaded", "used", "removed"):
            db_session.add(
                ToolUsageEvent(tool_id=only_other.id, event_type=et)
            )
        db_session.add(
            ToolUsageEvent(tool_id=with_rec.id, event_type="recommended")
        )
        db_session.commit()

        client = _client_with_session(db_session)
        items = client.get("/stats/top-tools").json()["items"]
        slugs = [it["slug"] for it in items]
        assert "only-other" not in slugs
        assert "with-rec" in slugs

    def test_response_shape_has_required_fields(self, db_session):
        tool = Tool(slug="t", name="The Tool", is_in_manifest=True)
        db_session.add(tool)
        db_session.flush()
        db_session.add(ToolUsageEvent(tool_id=tool.id, event_type="recommended"))
        db_session.commit()

        client = _client_with_session(db_session)
        items = client.get("/stats/top-tools").json()["items"]
        assert len(items) == 1
        entry = items[0]
        assert set(entry.keys()) == {"slug", "name", "times_recommended"}
        assert entry["slug"] == "t"
        assert entry["name"] == "The Tool"
        assert entry["times_recommended"] == 1
