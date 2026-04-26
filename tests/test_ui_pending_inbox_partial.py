"""Wiring tests for GET /partials/pending-inbox + POST
/partials/requests/{filename}/action — Day 10 Task 3.

Contracts under test:

1. **Empty state renders** — no pending requests → designed copy.
2. **Non-empty render** — cards show tool name, filename, action form
   wired with HTMX (target, swap, hx-post URL), three submit buttons
   (approve / deny / defer), and a comment textarea.
3. **Approve action** transitions request status pending → approved
   and returns a refreshed inbox without the just-approved request.
4. **Deny action** transitions pending → denied and returns refreshed
   inbox.
5. **Defer action** transitions pending → deferred and returns
   refreshed inbox.
6. **Unknown action** → 400.
7. **Unknown filename** → 404.
8. **SSE bridge wiring** — `/static/js/concierge.js` resolves and
   index.html includes the script tag so the EventSource shim runs
   at page load.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.config import Settings, get_settings
from core.db.session import get_db
from core.lifecycle_store.schema import NewRequestDraft
from core.lifecycle_store.service import LifecycleService
from ui.app import create_app as create_ui_app


@pytest.fixture
def inbox_harness(tmp_path, db_session):
    """Spin up a UI TestClient with lifecycle_root pointed at tmp_path
    + db_session injected. Returns (client, service, tmp_path) — the
    `service` is for seeding pending requests via create_request."""
    for folder in ("pending", "resolved", "archived"):
        (tmp_path / folder).mkdir()

    test_settings = Settings(lifecycle_root=tmp_path)

    app = create_ui_app()
    app.dependency_overrides[get_db] = lambda: (yield db_session)
    app.dependency_overrides[get_settings] = lambda: test_settings

    service = LifecycleService(
        session=db_session,
        lifecycle_root=tmp_path,
        install_dispatcher=lambda *args, **kwargs: None,
    )

    client = TestClient(app)
    return client, service, tmp_path


# ---- Empty state ----------------------------------------------------


class TestPendingInboxEmptyState:

    def test_empty_state_returns_200(self, inbox_harness):
        client, _svc, _root = inbox_harness
        resp = client.get("/partials/pending-inbox")
        assert resp.status_code == 200

    def test_empty_state_renders_designed_copy(self, inbox_harness):
        client, _svc, _root = inbox_harness
        body = client.get("/partials/pending-inbox").text
        assert "No pending tool requests" in body
        assert "empty-state--pending-inbox" in body


# ---- Non-empty render ----------------------------------------------


class TestPendingInboxNonEmptyRender:

    def test_renders_card_with_tool_name(self, inbox_harness):
        client, svc, _root = inbox_harness
        svc.create_request(
            NewRequestDraft(
                tool_name="csvkit", category="data", confidence="high"
            )
        )
        body = client.get("/partials/pending-inbox").text
        assert "csvkit" in body
        # Confidence badge surfaces when set
        assert "badge-confidence-high" in body

    def test_card_form_wires_htmx_attributes(self, inbox_harness):
        client, svc, _root = inbox_harness
        detail = svc.create_request(NewRequestDraft(tool_name="ripgrep"))
        body = client.get("/partials/pending-inbox").text
        assert (
            f'hx-post="/partials/requests/{detail.filename}/action"' in body
        )
        assert 'hx-target="#pending-inbox"' in body
        assert 'hx-swap="outerHTML"' in body

    def test_card_form_has_three_action_buttons_and_comment(
        self, inbox_harness
    ):
        client, svc, _root = inbox_harness
        svc.create_request(NewRequestDraft(tool_name="fd"))
        body = client.get("/partials/pending-inbox").text
        assert 'value="approve"' in body
        assert 'value="deny"' in body
        assert 'value="defer"' in body
        assert 'name="comment"' in body
        assert "<textarea" in body


# ---- Action POSTs --------------------------------------------------


class TestPendingInboxActions:

    def test_approve_returns_refreshed_inbox_without_resolved_request(
        self, inbox_harness
    ):
        client, svc, _root = inbox_harness
        detail = svc.create_request(NewRequestDraft(tool_name="ripgrep"))
        # Confirm request is in inbox before action
        before = client.get("/partials/pending-inbox").text
        assert "ripgrep" in before

        resp = client.post(
            f"/partials/requests/{detail.filename}/action",
            data={"action": "approve", "comment": "approved for v2"},
        )
        assert resp.status_code == 200
        # Returned body is the refreshed inbox; the just-approved
        # request transitioned to status='approved' so it falls out
        # of list_pending (which filters folder='pending' AND
        # status='pending').
        after = resp.text
        assert "Pending Requests" in after  # inbox header still present
        assert "ripgrep" not in after  # resolved request gone

    def test_deny_resolves_request_and_returns_inbox(self, inbox_harness):
        client, svc, _root = inbox_harness
        detail = svc.create_request(NewRequestDraft(tool_name="jq"))
        resp = client.post(
            f"/partials/requests/{detail.filename}/action",
            data={"action": "deny", "comment": "duplicate of existing tool"},
        )
        assert resp.status_code == 200
        assert "jq" not in resp.text

    def test_defer_resolves_request_and_returns_inbox(self, inbox_harness):
        client, svc, _root = inbox_harness
        detail = svc.create_request(NewRequestDraft(tool_name="bat"))
        resp = client.post(
            f"/partials/requests/{detail.filename}/action",
            data={"action": "defer", "comment": "revisit next week"},
        )
        assert resp.status_code == 200
        assert "bat" not in resp.text

    def test_action_without_comment_still_works(self, inbox_harness):
        client, svc, _root = inbox_harness
        detail = svc.create_request(NewRequestDraft(tool_name="hyperfine"))
        resp = client.post(
            f"/partials/requests/{detail.filename}/action",
            data={"action": "approve", "comment": ""},
        )
        assert resp.status_code == 200

    def test_unknown_action_returns_400(self, inbox_harness):
        client, svc, _root = inbox_harness
        detail = svc.create_request(NewRequestDraft(tool_name="exa"))
        resp = client.post(
            f"/partials/requests/{detail.filename}/action",
            data={"action": "shenanigans", "comment": ""},
        )
        assert resp.status_code == 400

    def test_unknown_filename_returns_404(self, inbox_harness):
        client, _svc, _root = inbox_harness
        resp = client.post(
            "/partials/requests/does-not-exist.md/action",
            data={"action": "approve", "comment": ""},
        )
        assert resp.status_code == 404


# ---- SSE bridge wiring ---------------------------------------------


class TestSseBridgeWiring:

    def test_concierge_js_resolves_from_static_mount(self, inbox_harness):
        client, _svc, _root = inbox_harness
        resp = client.get("/static/js/concierge.js")
        assert resp.status_code == 200
        # Spot-check: the bridge mentions /ui/events and the inbox
        # target; if either is missing, the SSE-driven refresh is
        # broken at the wire.
        body = resp.text
        assert "/ui/events" in body
        assert "/partials/pending-inbox" in body
        assert "new_request" in body

    def test_index_html_includes_concierge_js_script_tag(
        self, inbox_harness
    ):
        client, _svc, _root = inbox_harness
        body = client.get("/").text
        assert '/static/js/concierge.js' in body
