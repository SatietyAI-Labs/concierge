"""Tests for POST /requests, GET /requests/pending, GET /requests/{id},
POST /requests/{filename}/status — the N7 HTTP surface.

Router-level contract:

- POST /requests → 201 with RequestDetail
- GET /requests/pending → 200 with envelope
- GET /requests/{id} missing → 404 with structured detail
- POST /requests/{filename}/status:
  - legal transition → 200 with RequestDetail
  - illegal transition → 409 with `invalid_transition` error code
  - unknown filename → 404 with `request_not_found` error code
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
    """Spin up a TestClient wired to a tmp lifecycle_root and the
    in-memory db_session from conftest.
    """
    for folder in ("pending", "resolved", "archived"):
        (tmp_path / folder).mkdir()
    # Disable real subprocess dispatch for approve-path tests.
    service = LifecycleService(
        session=db_session,
        lifecycle_root=tmp_path,
        counters=LifecycleCounters(),
        install_dispatcher=lambda *args, **kwargs: None,
    )
    app = create_app()
    app.dependency_overrides[get_lifecycle_service] = lambda: service
    # Share the same db_session with any endpoints that call get_db.
    app.dependency_overrides[get_db] = lambda: (yield db_session)
    client = TestClient(app)
    return client, service, tmp_path


class TestCreate:
    def test_post_returns_201(self, api_harness):
        client, _svc, _root = api_harness
        resp = client.post(
            "/requests",
            json={"tool_name": "csvkit", "category": "data", "confidence": "high"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "pending"
        assert body["folder"] == "pending"
        assert body["tool_name"] == "csvkit"
        assert body["is_parseable"] is True

    def test_missing_tool_name_returns_422(self, api_harness):
        client, _svc, _root = api_harness
        resp = client.post("/requests", json={"category": "data"})
        assert resp.status_code == 422


class TestListPending:
    def test_empty_list(self, api_harness):
        client, _svc, _root = api_harness
        resp = client.get("/requests/pending")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0

    def test_populated_list(self, api_harness):
        client, svc, _root = api_harness
        svc.create_request(NewRequestDraft(tool_name="csvkit"))
        svc.create_request(NewRequestDraft(tool_name="ripgrep"))
        resp = client.get("/requests/pending")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        names = sorted(i["tool_name"] for i in body["items"])
        assert names == ["csvkit", "ripgrep"]


class TestGetDetail:
    def test_missing_id_404(self, api_harness):
        client, _svc, _root = api_harness
        resp = client.get("/requests/999999")
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"] == "request_not_found"

    def test_existing_detail_returns_raw_markdown(self, api_harness):
        client, svc, _root = api_harness
        detail = svc.create_request(NewRequestDraft(tool_name="csvkit"))
        resp = client.get(f"/requests/{detail.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["raw_markdown"]
        assert "# Tool Request: csvkit" in body["raw_markdown"]


class TestUpdateStatus:
    def test_legal_transition_200(self, api_harness):
        client, svc, _root = api_harness
        detail = svc.create_request(NewRequestDraft(tool_name="csvkit"))
        resp = client.post(
            f"/requests/{detail.filename}/status",
            json={"status": "approved"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "approved"

    def test_illegal_transition_409_with_code(self, api_harness):
        client, svc, _root = api_harness
        detail = svc.create_request(NewRequestDraft(tool_name="csvkit"))
        resp = client.post(
            f"/requests/{detail.filename}/status",
            json={"status": "installed"},  # illegal direct jump
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["error"] == "invalid_transition"

    def test_unknown_filename_404(self, api_harness):
        client, _svc, _root = api_harness
        resp = client.post(
            "/requests/nope.md/status", json={"status": "approved"}
        )
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"] == "request_not_found"
