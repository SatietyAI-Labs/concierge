"""N8 — end-to-end roundtrip smoke over the fixture corpus.

Part of the **operational baseline for soak diagnostics**: this test
walks the full lifecycle flow (write fixture → GET → POST status →
re-GET → verify status change) using the canonical
`planning/test-fixtures/sample-tool-request.md`. During the 48h
shakedown, replaying this sequence against a live Concierge is the
fastest check that lifecycle endpoints + cron-compatible writes +
parser tolerance are all still holding.

Also exercises **Risk #5 parser robustness**: plants a malformed
.md in the pending/ folder mid-test and asserts the list endpoint
surfaces it as `is_parseable=False` rather than 500ing.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core.api.requests import get_lifecycle_service
from core.app import create_app
from core.db.session import get_db
from core.lifecycle_store.service import (
    LifecycleService,
    reset_counters_for_tests,
)
from core.lifecycle_store.store import reconcile as reconcile_lifecycle


FIXTURES = Path(__file__).resolve().parent.parent / "planning" / "test-fixtures"


@pytest.fixture
def roundtrip_client(tmp_path, db_session):
    for folder in ("pending", "resolved", "archived"):
        (tmp_path / folder).mkdir()
    # Reset the module-level lifecycle-counters singleton so /health
    # reads a known starting state; the service's counters default
    # to this same singleton via __post_init__.
    reset_counters_for_tests()

    # Disable real subprocess dispatch for the approve path — smoke
    # tests shouldn't run pip/npm. Dedicated X13 wire-in tests in
    # test_lifecycle_service.py cover the dispatch contract.
    service = LifecycleService(
        session=db_session,
        lifecycle_root=tmp_path,
        install_dispatcher=lambda *args, **kwargs: None,
    )
    app = create_app()
    app.dependency_overrides[get_lifecycle_service] = lambda: service
    app.dependency_overrides[get_db] = lambda: (yield db_session)
    client = TestClient(app)
    return client, service, tmp_path


def _plant_and_reconcile(root: Path, db_session, src: Path, filename: str) -> Path:
    """Copy a fixture file into the lifecycle tree and run
    reconciliation so the DB row exists. Simulates the startup
    reconcile pass for a file that wasn't there at service init.
    """
    dst = root / "pending" / filename
    shutil.copy(src, dst)
    reconcile_lifecycle(db_session, root)
    return dst


class TestFixtureAvailability:
    """Pin the canonical fixture corpus. Missing fixtures = missing
    soak baseline = operator can't bisect.
    """

    def test_sample_tool_request_exists(self):
        assert (FIXTURES / "sample-tool-request.md").exists()

    def test_sample_task_exists(self):
        assert (FIXTURES / "sample-task.md").exists()

    def test_sample_csv_exists(self):
        assert (FIXTURES / "sample-csv.csv").exists()

    def test_sample_catalog_state_exists(self):
        assert (FIXTURES / "sample-catalog-state.json").exists()

    def test_expected_recommendation_exists(self):
        assert (FIXTURES / "expected-recommendation.md").exists()


class TestRoundtripHappyPath:
    """write fixture → GET /requests/pending → POST status → re-GET
    → verify status changed. Mirrors the sequence the UI (and an
    operator curling directly) will execute during soak.
    """

    def test_fixture_roundtrip(self, roundtrip_client, db_session):
        client, _svc, root = roundtrip_client

        # Copy the canonical fixture into the live lifecycle root
        # and reconcile so the DB row exists (simulates startup).
        filename = "2026-04-22-smoke-csvkit.md"  # deterministic for assertion
        dst = _plant_and_reconcile(
            root, db_session, FIXTURES / "sample-tool-request.md", filename
        )

        # GET pending: fixture visible as a parseable row
        resp = client.get("/requests/pending")
        assert resp.status_code == 200
        body = resp.json()
        filenames = [i["filename"] for i in body["items"]]
        assert filename in filenames
        fixture_entry = next(i for i in body["items"] if i["filename"] == filename)
        assert fixture_entry["is_parseable"] is True
        assert fixture_entry["status"] == "pending"
        assert fixture_entry["tool_name"] == "csvkit"

        # POST status: legal transition pending → approved
        resp = client.post(
            f"/requests/{filename}/status", json={"status": "approved"}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

        # Re-read the file directly — status line must be updated in
        # place so the cron (X11) sees it.
        raw = dst.read_text(encoding="utf-8")
        assert raw.startswith("status: approved\n")

        # Re-GET pending: the fixture is no longer pending-status,
        # so it drops out of the pending list.
        resp = client.get("/requests/pending")
        body = resp.json()
        pending_names = [i["filename"] for i in body["items"]]
        assert filename not in pending_names


class TestRoundtripBadFileInjection:
    """Operational-first assertion: a malformed file in pending/
    must NOT prevent the list endpoint from surfacing the good files
    alongside an `is_parseable=False` marker for the bad one.
    """

    def test_bad_file_surfaces_as_unparseable_not_500(
        self, roundtrip_client, db_session
    ):
        client, _svc, root = roundtrip_client

        good_name = "2026-04-22-smoke-good.md"
        _plant_and_reconcile(
            root, db_session, FIXTURES / "sample-tool-request.md", good_name
        )

        # Inject a malformed file AFTER reconcile — it has no DB
        # row; the list endpoint must still surface it via the
        # filesystem parseability snapshot, flagged unparseable.
        bad_name = "2026-04-22-smoke-malformed.md"
        (root / "pending" / bad_name).write_text(
            "this file is not a valid tool request at all\n", encoding="utf-8"
        )

        resp = client.get("/requests/pending")
        assert resp.status_code == 200
        body = resp.json()

        by_name = {i["filename"]: i for i in body["items"]}
        assert good_name in by_name
        assert bad_name in by_name

        # Good file parseable; bad file flagged; endpoint stayed up.
        assert by_name[good_name]["is_parseable"] is True
        assert by_name[bad_name]["is_parseable"] is False
        assert by_name[bad_name]["parse_error"] is not None

    def test_bad_file_does_not_block_status_update_on_good_file(
        self, roundtrip_client, db_session
    ):
        """Even with a sibling unparseable file present, a POST
        status on the good file must succeed. The bad file is
        isolated; it doesn't contaminate the folder-agnostic
        lookup or the DB sync path.
        """
        client, _svc, root = roundtrip_client
        good_name = "2026-04-22-smoke-good.md"
        _plant_and_reconcile(
            root, db_session, FIXTURES / "sample-tool-request.md", good_name
        )
        (root / "pending" / "bad.md").write_text("garbage\n", encoding="utf-8")

        resp = client.post(
            f"/requests/{good_name}/status", json={"status": "approved"}
        )
        assert resp.status_code == 200


class TestHealthReflectsSmokeActivity:
    """After a roundtrip, /health's counters must increment so an
    operator curling `/health | jq .counters` can see the activity
    without reading logs.
    """

    def test_lifecycle_transition_bumps_counter(
        self, roundtrip_client, db_session
    ):
        client, _svc, root = roundtrip_client
        good_name = "2026-04-22-smoke-counter.md"
        _plant_and_reconcile(
            root, db_session, FIXTURES / "sample-tool-request.md", good_name
        )

        before = client.get("/health").json()["counters"]["lifecycle"]["transitioned"]
        resp = client.post(
            f"/requests/{good_name}/status", json={"status": "approved"}
        )
        assert resp.status_code == 200, resp.text
        after = client.get("/health").json()["counters"]["lifecycle"]["transitioned"]

        assert after == before + 1
