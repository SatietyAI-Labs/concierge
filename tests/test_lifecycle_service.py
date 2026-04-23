"""Tests for core.lifecycle_store.service — orchestration + logging.

Covers:

- create_request: file + DB row land consistently; INFO log with
  filename + tool_slug
- update_status: INFO log with old_status → new_status + folder;
  folder-agnostic lookup after simulated cron move
- Invalid transition raises with counter bump
- Filename collision produces a unique disambiguation (never
  overwrites)
- One-bad-file does not block list_pending (service-layer merge)
"""
from __future__ import annotations

import logging
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from core.lifecycle_store.schema import NewRequestDraft, StatusChange
from core.lifecycle_store.service import (
    LifecycleCounters,
    LifecycleService,
    RequestNotFoundError,
    reset_counters_for_tests,
)
from core.lifecycle_store.transitions import InvalidTransitionError


@pytest.fixture
def lifecycle_root(tmp_path) -> Path:
    for folder in ("pending", "resolved", "archived"):
        (tmp_path / folder).mkdir()
    return tmp_path


@pytest.fixture
def service(db_session: Session, lifecycle_root: Path) -> LifecycleService:
    reset_counters_for_tests()
    # Disable real subprocess dispatch — tests of the generic
    # update_status flow don't want to hit pip/npm. Tests that
    # specifically exercise the X13 wire-in construct their own
    # LifecycleService with a purpose-built mock dispatcher.
    return LifecycleService(
        session=db_session,
        lifecycle_root=lifecycle_root,
        counters=LifecycleCounters(),
        install_dispatcher=lambda *args, **kwargs: None,
    )


# ---- create_request ------------------------------------------------------


class TestCreateRequest:
    def test_happy_path_writes_file_and_row(
        self, service: LifecycleService, lifecycle_root: Path, db_session: Session
    ):
        detail = service.create_request(
            NewRequestDraft(
                tool_name="csvkit",
                category="data",
                install_method="pip-user",
                task_context="Analyzing CSV.",
                why_this_tool="Lightweight.",
                confidence="high",
            )
        )
        assert detail.status == "pending"
        assert detail.folder == "pending"
        assert detail.tool_name == "csvkit"
        assert detail.tool_slug == "csvkit"
        assert detail.is_parseable is True
        assert detail.raw_markdown and "# Tool Request: csvkit" in detail.raw_markdown

        # File exists
        pending_files = list((lifecycle_root / "pending").glob("*.md"))
        assert len(pending_files) == 1
        # DB row exists
        from core.db.models import Request

        rows = db_session.query(Request).all()
        assert len(rows) == 1

    def test_create_emits_info_log(
        self, service: LifecycleService, caplog
    ):
        with caplog.at_level(logging.INFO, logger="core.lifecycle_store.service"):
            service.create_request(NewRequestDraft(tool_name="csvkit"))
        infos = [r for r in caplog.records if r.levelno == logging.INFO]
        matching = [r for r in infos if "lifecycle.create" in r.getMessage()]
        assert len(matching) == 1
        assert "tool_slug=csvkit" in matching[0].getMessage()

    def test_create_bumps_counter(self, service: LifecycleService):
        service.create_request(NewRequestDraft(tool_name="csvkit"))
        snap = service.counters.snapshot()
        assert snap["created"] == 1

    def test_filename_collision_disambiguates(
        self, service: LifecycleService, lifecycle_root: Path
    ):
        """Two requests for the same tool in the same minute must
        produce distinct filenames, not collide.
        """
        a = service.create_request(NewRequestDraft(tool_name="csvkit"))
        b = service.create_request(NewRequestDraft(tool_name="csvkit"))
        assert a.filename != b.filename
        # Disambiguation suffix of the form `-2.md`, `-3.md`, ...
        assert b.filename.endswith("-2.md")


# ---- update_status -------------------------------------------------------


class TestUpdateStatus:
    def _existing(self, service: LifecycleService) -> str:
        detail = service.create_request(NewRequestDraft(tool_name="csvkit"))
        return detail.filename

    def test_pending_to_approved(self, service: LifecycleService, caplog):
        filename = self._existing(service)
        with caplog.at_level(logging.INFO, logger="core.lifecycle_store.service"):
            detail = service.update_status(
                filename=filename,
                change=StatusChange(status="approved"),
            )
        assert detail.status == "approved"
        # Log line records old → new + folder
        matching = [
            r.getMessage()
            for r in caplog.records
            if "lifecycle.transition" in r.getMessage()
        ]
        assert len(matching) == 1
        assert "old_status=pending" in matching[0]
        assert "new_status=approved" in matching[0]
        assert f"filename={filename}" in matching[0]

    def test_illegal_transition_raises_and_logs_warning(
        self, service: LifecycleService, caplog
    ):
        filename = self._existing(service)
        with caplog.at_level(logging.WARNING, logger="core.lifecycle_store.service"):
            with pytest.raises(InvalidTransitionError):
                service.update_status(
                    filename=filename,
                    change=StatusChange(status="installed"),  # direct jump illegal
                )
        warns = [
            r.getMessage()
            for r in caplog.records
            if r.levelno == logging.WARNING and "invalid_transition" in r.getMessage()
        ]
        assert len(warns) == 1
        # Counter bumped
        snap = service.counters.snapshot()
        assert snap["invalid_transitions"] == 1

    def test_unknown_filename_raises_not_found(self, service: LifecycleService):
        with pytest.raises(RequestNotFoundError):
            service.update_status(
                filename="nope.md",
                change=StatusChange(status="approved"),
            )
        snap = service.counters.snapshot()
        assert snap["not_found"] == 1

    def test_folder_agnostic_lookup_after_cron_move(
        self, service: LifecycleService, lifecycle_root: Path
    ):
        """Create a pending request, approve it, then simulate the
        cron moving it to resolved/ (what X11 does). A second
        status update must still find and update the file in its
        new home.
        """
        filename = self._existing(service)
        service.update_status(
            filename=filename, change=StatusChange(status="approved")
        )
        # Simulate cron rename
        src = lifecycle_root / "pending" / filename
        dst = lifecycle_root / "resolved" / filename
        src.rename(dst)

        detail = service.update_status(
            filename=filename, change=StatusChange(status="installed")
        )
        assert detail.status == "installed"
        assert detail.folder == "resolved"


# ---- list_pending (parseability isolation) ------------------------------


class TestListPending:
    def test_bad_file_does_not_block_good_files(
        self, service: LifecycleService, lifecycle_root: Path
    ):
        # One good request via service
        service.create_request(NewRequestDraft(tool_name="csvkit"))
        # One bad file dropped in directly
        (lifecycle_root / "pending" / "malformed.md").write_text(
            "not a valid request file\n"
        )
        items = service.list_pending()
        # Good file present (parseable), bad file present (unparseable
        # via snapshot overlay).
        by_name = {i.filename: i for i in items}
        assert any(n.endswith("csvkit.md") for n in by_name)
        assert "malformed.md" in by_name
        assert by_name["malformed.md"].is_parseable is False
        assert by_name["malformed.md"].parse_error is not None


# ---- X13 wire-in: approve triggers install --------------------------------


def _make_service_with_dispatcher(
    db_session: Session, lifecycle_root: Path, dispatcher
) -> LifecycleService:
    reset_counters_for_tests()
    return LifecycleService(
        session=db_session,
        lifecycle_root=lifecycle_root,
        counters=LifecycleCounters(),
        install_dispatcher=dispatcher,
    )


def _make_install_result(
    *, method: str = "pip_user", success: bool = True, returncode: int = 0
):
    from core.install.schemas import InstallResult

    return InstallResult(
        method=method,
        command="pip install --user csvkit",
        success=success,
        returncode=returncode,
        stdout="",
        stderr="" if success else "ERROR: could not find csvkit",
        elapsed_ms=321,
    )


class TestApproveTriggersInstall:
    """X13 wire-in: `update_status(..., 'approved')` with a canonical
    install_method dispatches install and auto-transitions to
    installed (success) or failed (failure).
    """

    def test_canonical_method_installs_and_transitions_to_installed(
        self, db_session, lifecycle_root
    ):
        calls = []

        def dispatcher(method, *, tool_name, **kw):
            calls.append((method, tool_name))
            return _make_install_result(success=True)

        svc = _make_service_with_dispatcher(db_session, lifecycle_root, dispatcher)
        filename = svc.create_request(
            NewRequestDraft(tool_name="csvkit", install_method="pip-user")
        ).filename

        detail = svc.update_status(
            filename=filename, change=StatusChange(status="approved")
        )

        assert len(calls) == 1
        assert calls[0][1] == "csvkit"
        assert detail.status == "installed"
        # Install section now present in the file's raw_markdown
        assert "## Install" in detail.raw_markdown
        assert "pip install --user csvkit" in detail.raw_markdown
        assert "exit=0" in detail.raw_markdown

    def test_install_failure_transitions_to_failed(
        self, db_session, lifecycle_root
    ):
        def dispatcher(method, *, tool_name, **kw):
            return _make_install_result(success=False, returncode=1)

        svc = _make_service_with_dispatcher(db_session, lifecycle_root, dispatcher)
        filename = svc.create_request(
            NewRequestDraft(tool_name="csvkit", install_method="pip-user")
        ).filename

        detail = svc.update_status(
            filename=filename, change=StatusChange(status="approved")
        )

        assert detail.status == "failed"
        assert "## Install" in detail.raw_markdown
        assert "exit=1" in detail.raw_markdown

    def test_non_canonical_method_leaves_status_approved(
        self, db_session, lifecycle_root
    ):
        calls = []

        def dispatcher(*args, **kwargs):
            calls.append(args)
            return _make_install_result(success=True)

        svc = _make_service_with_dispatcher(db_session, lifecycle_root, dispatcher)
        filename = svc.create_request(
            NewRequestDraft(tool_name="some-service", install_method="api-key")
        ).filename

        detail = svc.update_status(
            filename=filename, change=StatusChange(status="approved")
        )

        assert detail.status == "approved"
        # Dispatcher was never called — non-canonical method skips X13
        assert calls == []
        # No Install section written
        assert "## Install" not in detail.raw_markdown

    def test_dispatcher_exception_leaves_status_approved(
        self, db_session, lifecycle_root, caplog
    ):
        def boom(*args, **kwargs):
            raise RuntimeError("subprocess exploded")

        svc = _make_service_with_dispatcher(db_session, lifecycle_root, boom)
        filename = svc.create_request(
            NewRequestDraft(tool_name="csvkit", install_method="pip-user")
        ).filename

        with caplog.at_level(logging.ERROR, logger="core.lifecycle_store.service"):
            detail = svc.update_status(
                filename=filename, change=StatusChange(status="approved")
            )

        assert detail.status == "approved"
        assert any(
            "install_dispatch_failed" in r.getMessage() for r in caplog.records
        )
        assert "## Install" not in detail.raw_markdown
