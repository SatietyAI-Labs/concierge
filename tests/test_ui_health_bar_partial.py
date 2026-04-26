"""Wiring tests for GET /partials/health-bar — Day 10 Task 1.

Contracts under test:

1. **Renders against composed data sources.** The partial fetches
   `/health` payload + `/stats/top-tools` via direct handler calls
   and returns rendered HTML. Marker strings from each source must
   be visible in the response body.

2. **HTMX polling wired in template.** The rendered HTML carries
   `hx-get="/partials/health-bar"` + `hx-trigger="every 10s"` +
   `hx-swap="outerHTML"` so the operator's dashboard refreshes
   without page reload.

3. **Top-3 list renders when recommendations exist.**

4. **Empty state renders when no recommendations exist** — the
   designed-empty-state philosophy carried into v0.1 dashboard
   panels (Day 10 alignment Real Check 1 + Pending Inbox extension).

5. **Status quo data flows through:** tile labels for status,
   catalog counts, pending requests, scanner heartbeat all render
   to the page without template-render errors.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from core.db.models import Tool, ToolUsageEvent
from core.db.session import get_db
from ui.app import create_app as create_ui_app


def _ui_client(db_session) -> TestClient:
    """Build a fresh ui.create_app() TestClient with the supplied
    db_session injected via dependency override."""
    app = create_ui_app()
    app.dependency_overrides[get_db] = lambda: (yield db_session)
    return TestClient(app)


class TestHealthBarPartial:

    def test_returns_200_against_empty_db(self, db_session):
        """Empty DB → partial renders with empty-state messaging,
        no errors."""
        client = _ui_client(db_session)
        resp = client.get("/partials/health-bar")
        assert resp.status_code == 200

    def test_carries_htmx_polling_attributes(self, db_session):
        """The rendered partial must wire its own 10s polling so
        the dashboard refreshes without page reload."""
        client = _ui_client(db_session)
        body = client.get("/partials/health-bar").text
        assert 'hx-get="/partials/health-bar"' in body
        assert 'hx-trigger="every 10s"' in body
        assert 'hx-swap="outerHTML"' in body

    def test_renders_status_tile(self, db_session):
        client = _ui_client(db_session)
        body = client.get("/partials/health-bar").text
        assert "Status" in body
        # /health returns "ok" on the happy path; tile renders that
        # value in a `.health-value` slot.
        assert "ok" in body

    def test_renders_catalog_and_pending_tiles(self, db_session):
        client = _ui_client(db_session)
        body = client.get("/partials/health-bar").text
        assert "Catalog" in body
        assert "Pending requests" in body
        # Empty DB → 0 total tools, 0 pending requests; both should
        # render numerically (0) without crashing on missing fields.
        assert "active" in body  # "{tools_active} active / {tools} total"

    def test_renders_scanner_tile_not_yet_run_when_state_absent(
        self, db_session
    ):
        """`request.app.state.last_scanner_summary` is unset outside
        of lifespan; the tile must render the not-yet-run branch
        rather than crashing on the missing attribute."""
        client = _ui_client(db_session)
        body = client.get("/partials/health-bar").text
        assert "Scanner" in body
        assert "not yet run" in body

    def test_top_3_renders_when_recommendations_exist(self, db_session):
        """With recommendations seeded, the top-tools tile should show
        an ordered list with names + counts."""
        ripgrep = Tool(slug="ripgrep", name="ripgrep", is_in_manifest=True)
        fd = Tool(slug="fd", name="fd", is_in_manifest=True)
        db_session.add_all([ripgrep, fd])
        db_session.flush()
        for _ in range(4):
            db_session.add(
                ToolUsageEvent(tool_id=ripgrep.id, event_type="recommended")
            )
        db_session.add(ToolUsageEvent(tool_id=fd.id, event_type="recommended"))
        db_session.commit()

        client = _ui_client(db_session)
        body = client.get("/partials/health-bar").text
        assert "Top-3 most-recommended" in body
        assert "ripgrep" in body
        assert "×4" in body  # times_recommended for ripgrep
        assert "fd" in body
        assert "×1" in body  # times_recommended for fd
        assert "No recommendations yet" not in body

    def test_top_3_empty_state_renders_when_no_recommendations(
        self, db_session
    ):
        """Designed empty state per Day 10 alignment Real Check 1
        philosophy carried into v0.1 dashboard panels."""
        client = _ui_client(db_session)
        body = client.get("/partials/health-bar").text
        assert "Top-3 most-recommended" in body
        assert "No recommendations yet" in body

    def test_pending_tile_renders_status_count_in_drift_case(
        self, db_session
    ):
        """Day 11 Task 1.3 / Fork D1: the rendered partial's
        Pending requests tile must show the inbox-aligned count
        in the canonical drift case (folder=pending rows whose
        status has moved on without cron reconciliation).

        Three rows in folder=pending, only one with status=pending.
        Tile must render '1' inside the .health-value slot, not '3'.
        Locks the operator-observable claim — same number on the
        bar as on the inbox card list."""
        from core.db.models import Request as RequestRow

        db_session.add_all([
            RequestRow(
                filename="2026-04-26-0001-csvkit.md",
                status="pending", folder="pending",
                tool_name="csvkit", raw_markdown="# csvkit",
            ),
            RequestRow(
                filename="2026-04-26-0002-ripgrep.md",
                status="failed", folder="pending",
                tool_name="ripgrep", raw_markdown="# ripgrep",
            ),
            RequestRow(
                filename="2026-04-26-0003-ocrmypdf.md",
                status="installed", folder="pending",
                tool_name="ocrmypdf", raw_markdown="# ocrmypdf",
            ),
        ])
        db_session.commit()

        client = _ui_client(db_session)
        body = client.get("/partials/health-bar").text
        assert "Pending requests" in body
        # Inbox-aligned count: 1 (only the status=pending row)
        assert '<span class="health-value">1</span>' in body
        # Folder-only would render 3 — assert that's not what shows
        assert '<span class="health-value">3</span>' not in body
