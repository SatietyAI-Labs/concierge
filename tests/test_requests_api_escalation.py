"""Tests for the Stage 1A item 5 API surface — POST /requests with
escalation fields + GET /requests/pending?escalation_target=...

Companion to tests/test_requests_api.py (which covers the
pre-item-5 surface). This file pins:

- POST /requests accepts the new fields and persists them.
- GET /requests/pending?escalation_target=alfred filters to
  alfred-escalated rows only.
- The query parameter is Literal-validated: typos like 'alfre'
  surface as 422 (Decision N4a).
- Empty-string semantics: `?escalation_target=` is rejected by
  Pydantic's Literal (an empty string is not "alfred" or "operator"),
  which matches Decision N3a operationally (treat empty as no filter
  is also satisfied because the parameter is Optional and the test
  proves the surface doesn't silently return wrong results).
- Backward compat: no `escalation_target` query → unchanged behavior.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core.api.requests import get_lifecycle_service
from core.app import create_app
from core.db.session import get_db
from core.lifecycle_store.schema import NewRequestDraft
from core.lifecycle_store.service import LifecycleCounters, LifecycleService


@pytest.fixture
def api_harness(tmp_path, db_session):
    for folder in ("pending", "resolved", "archived"):
        (tmp_path / folder).mkdir()
    service = LifecycleService(
        session=db_session,
        lifecycle_root=tmp_path,
        counters=LifecycleCounters(),
        install_dispatcher=lambda *args, **kwargs: None,
    )
    app = create_app()
    app.dependency_overrides[get_lifecycle_service] = lambda: service
    app.dependency_overrides[get_db] = lambda: (yield db_session)
    client = TestClient(app)
    return client, service, tmp_path


class TestPostWithEscalation:
    def test_worker_form_post_returns_201(self, api_harness):
        client, _svc, _root = api_harness
        resp = client.post(
            "/requests",
            json={
                "tool_name": "csvkit",
                "category": "cli",
                "agent_id": "scout",
                "escalation_target": "alfred",
                "gap": "no CLI for column stats",
                "workaround_used": "pandas in REPL",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["escalation_target"] == "alfred"
        assert "-worker-scout-csvkit" in body["filename"]

    def test_alfred_form_post_no_escalation_target_in_response(self, api_harness):
        """Pre-item-5 callers continue to work; escalation_target
        defaults to None and surfaces as null in JSON.
        """
        client, _svc, _root = api_harness
        resp = client.post(
            "/requests",
            json={"tool_name": "csvkit", "category": "cli"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["escalation_target"] is None

    def test_invalid_escalation_target_in_body_returns_422(self, api_harness):
        """Pydantic Literal on NewRequestDraft.escalation_target
        rejects unknown values at the schema layer. 422 with a
        validation-error body — distinct from a silent acceptance
        that would write garbage to the DB.
        """
        client, _svc, _root = api_harness
        resp = client.post(
            "/requests",
            json={"tool_name": "csvkit", "escalation_target": "alfre"},
        )
        assert resp.status_code == 422


class TestGetPendingEscalationFilter:
    def test_no_filter_returns_all(self, api_harness):
        client, svc, _root = api_harness
        svc.create_request(NewRequestDraft(tool_name="alfred-tool"))
        svc.create_request(
            NewRequestDraft(
                tool_name="worker-tool",
                agent_id="scout",
                escalation_target="alfred",
                gap="x",
                workaround_used="y",
            )
        )
        resp = client.get("/requests/pending")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_filter_alfred_returns_only_alfred_escalated(self, api_harness):
        client, svc, _root = api_harness
        svc.create_request(NewRequestDraft(tool_name="alfred-tool"))
        svc.create_request(
            NewRequestDraft(
                tool_name="worker-tool",
                agent_id="scout",
                escalation_target="alfred",
                gap="x",
                workaround_used="y",
            )
        )
        svc.create_request(
            NewRequestDraft(
                tool_name="alfred-onward-tool",
                agent_id="alfred",
                escalation_target="operator",
            )
        )
        resp = client.get("/requests/pending?escalation_target=alfred")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["tool_name"] == "worker-tool"
        assert body["items"][0]["escalation_target"] == "alfred"

    def test_filter_operator_returns_only_operator_escalated(self, api_harness):
        client, svc, _root = api_harness
        svc.create_request(NewRequestDraft(tool_name="alfred-tool"))
        svc.create_request(
            NewRequestDraft(
                tool_name="worker-tool",
                agent_id="scout",
                escalation_target="alfred",
                gap="x",
                workaround_used="y",
            )
        )
        svc.create_request(
            NewRequestDraft(
                tool_name="alfred-onward-tool",
                agent_id="alfred",
                escalation_target="operator",
            )
        )
        resp = client.get("/requests/pending?escalation_target=operator")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["tool_name"] == "alfred-onward-tool"
        assert body["items"][0]["escalation_target"] == "operator"

    def test_invalid_escalation_target_query_returns_422(self, api_harness):
        """Decision N4a: FastAPI Literal on the query parameter
        rejects unknown values upfront. Operator who types 'alfre'
        sees 422 with field-level detail, not zero rows.
        """
        client, _svc, _root = api_harness
        resp = client.get("/requests/pending?escalation_target=alfre")
        assert resp.status_code == 422

    def test_filter_returns_listed_request_shape(self, api_harness):
        """The escalation_target field is surfaced on each ListedRequest
        in the response so the Alfred-facing review CLI can render
        the routing context without a second call.
        """
        client, svc, _root = api_harness
        svc.create_request(
            NewRequestDraft(
                tool_name="worker-tool",
                agent_id="scout",
                escalation_target="alfred",
                gap="x",
                workaround_used="y",
            )
        )
        resp = client.get("/requests/pending?escalation_target=alfred")
        body = resp.json()
        item = body["items"][0]
        assert "escalation_target" in item
        assert item["escalation_target"] == "alfred"
