"""Tests for core.lifecycle_store.store — reconcile, folder-agnostic
lookup, parseability-isolating list.

The adversarial surface here: a malformed file in pending/ MUST NOT
prevent listing the rest.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from core.db.models import Request
from core.lifecycle_store.store import (
    find_file_by_filename,
    list_parseability_snapshot,
    list_pending_rows,
    reconcile,
    row_detail,
)


# ---- Fixtures ------------------------------------------------------------


def _good_request(tool_name: str, status: str = "pending") -> str:
    return (
        f"status: {status}\n"
        "\n"
        f"# Tool Request: {tool_name}\n"
        "\n"
        "## Request\n"
        "\n"
        "- **Category:** data\n"
        f"- **Tool suggested:** {tool_name}\n"
        "- **Discovered:** false\n"
        "\n"
        "## Recommendation\n"
        "\n"
        "- **Confidence:** high\n"
    )


@pytest.fixture
def lifecycle_root(tmp_path) -> Path:
    for folder in ("pending", "resolved", "archived"):
        (tmp_path / folder).mkdir()
    return tmp_path


# ---- Reconcile -----------------------------------------------------------


class TestReconcile:
    def test_reconcile_empty_tree(self, lifecycle_root, db_session: Session):
        stats = reconcile(db_session, lifecycle_root)
        assert stats.scanned == 0
        assert stats.inserted == 0
        assert stats.unparseable == 0

    def test_reconcile_inserts_missing_rows(self, lifecycle_root, db_session: Session):
        (lifecycle_root / "pending" / "2026-04-22-0900-csvkit.md").write_text(
            _good_request("csvkit")
        )
        (lifecycle_root / "resolved" / "2026-04-20-1200-ripgrep.md").write_text(
            _good_request("ripgrep", status="installed")
        )
        stats = reconcile(db_session, lifecycle_root)
        assert stats.scanned == 2
        assert stats.inserted == 2
        assert stats.unparseable == 0
        rows = db_session.query(Request).all()
        assert len(rows) == 2

    def test_reconcile_is_idempotent(self, lifecycle_root, db_session: Session):
        (lifecycle_root / "pending" / "x.md").write_text(_good_request("x"))
        reconcile(db_session, lifecycle_root)
        # Second pass updates rather than duplicates.
        stats = reconcile(db_session, lifecycle_root)
        assert stats.scanned == 1
        assert stats.inserted == 0
        assert stats.updated == 1
        rows = db_session.query(Request).all()
        assert len(rows) == 1

    def test_reconcile_logs_unparseable_as_warning(
        self, lifecycle_root, db_session: Session, caplog
    ):
        (lifecycle_root / "pending" / "good.md").write_text(_good_request("good"))
        (lifecycle_root / "pending" / "bad.md").write_text("no status line here\n")
        with caplog.at_level(logging.WARNING, logger="core.lifecycle_store.store"):
            stats = reconcile(db_session, lifecycle_root)
        assert stats.scanned == 2
        assert stats.inserted == 1  # only the good one
        assert stats.unparseable == 1
        warns = [
            r
            for r in caplog.records
            if r.levelno == logging.WARNING
            and "lifecycle.reconcile.unparseable" in r.getMessage()
        ]
        assert len(warns) == 1
        assert "bad.md" in warns[0].getMessage()

    def test_reconcile_missing_root_does_not_crash(self, tmp_path, db_session: Session):
        missing = tmp_path / "does-not-exist"
        stats = reconcile(db_session, missing)
        assert stats.scanned == 0


# ---- Folder-agnostic lookup ---------------------------------------------


class TestFindFileByFilename:
    def test_finds_in_pending(self, lifecycle_root):
        (lifecycle_root / "pending" / "x.md").write_text("status: pending\n")
        result = find_file_by_filename(lifecycle_root, "x.md")
        assert result is not None
        path, folder = result
        assert folder == "pending"
        assert path.name == "x.md"

    def test_finds_after_cron_like_move(self, lifecycle_root):
        """Simulate cron having moved a file from pending/ to
        resolved/ between list time and POST time. The service layer
        calls this helper; it must locate the file in its new home.
        """
        src = lifecycle_root / "pending" / "x.md"
        src.write_text("status: approved\n")
        # Simulate the cron's rename.
        dst = lifecycle_root / "resolved" / "x.md"
        src.rename(dst)

        result = find_file_by_filename(lifecycle_root, "x.md")
        assert result is not None
        _, folder = result
        assert folder == "resolved"

    def test_returns_none_if_missing(self, lifecycle_root):
        assert find_file_by_filename(lifecycle_root, "nope.md") is None


# ---- Parseability snapshot ----------------------------------------------


class TestParseabilitySnapshot:
    def test_surfaces_unparseable_files(self, lifecycle_root):
        (lifecycle_root / "pending" / "good.md").write_text(_good_request("good"))
        (lifecycle_root / "pending" / "bad.md").write_text("no status here\n")
        snapshot = list_parseability_snapshot(lifecycle_root)
        # Only unparseable files should be in the snapshot; the
        # good ones come from DB listing.
        filenames = {r.filename for r in snapshot}
        assert "bad.md" in filenames
        assert "good.md" not in filenames
        bad = next(r for r in snapshot if r.filename == "bad.md")
        assert bad.is_parseable is False
        assert bad.parse_error is not None
        assert bad.folder == "pending"

    def test_empty_tree_returns_empty_list(self, lifecycle_root):
        assert list_parseability_snapshot(lifecycle_root) == []


# ---- DB listing --------------------------------------------------------


class TestListPendingRows:
    def test_returns_only_pending_folder_and_status(
        self, lifecycle_root, db_session: Session
    ):
        (lifecycle_root / "pending" / "p.md").write_text(_good_request("p"))
        (lifecycle_root / "resolved" / "r.md").write_text(
            _good_request("r", status="installed")
        )
        reconcile(db_session, lifecycle_root)
        rows = list_pending_rows(db_session)
        assert [r.filename for r in rows] == ["p.md"]

    def test_stale_only_filter(self, lifecycle_root, db_session: Session):
        """Filename timestamps drive age_days; stale=True filters
        to files >= STALE_PENDING_DAYS old.
        """
        from core.lifecycle_policy import STALE_PENDING_DAYS

        # Old file — clearly past STALE_PENDING_DAYS
        old_fn = "2020-01-01-0900-old.md"
        (lifecycle_root / "pending" / old_fn).write_text(_good_request("old"))
        # Today's file — not stale
        from datetime import datetime

        today_fn = f"{datetime.now():%Y-%m-%d-%H%M}-fresh.md"
        (lifecycle_root / "pending" / today_fn).write_text(_good_request("fresh"))

        reconcile(db_session, lifecycle_root)
        stale_rows = list_pending_rows(db_session, stale_only=True)
        assert [r.filename for r in stale_rows] == [old_fn]
        # Sanity: non-stale call returns both
        all_rows = list_pending_rows(db_session, stale_only=False)
        assert len(all_rows) == 2


# ---- Detail --------------------------------------------------------------


class TestRowDetail:
    def test_returns_detail_with_raw_markdown(
        self, lifecycle_root, db_session: Session
    ):
        (lifecycle_root / "pending" / "x.md").write_text(_good_request("x"))
        reconcile(db_session, lifecycle_root)
        row = db_session.query(Request).one()
        detail = row_detail(db_session, row.id)
        assert detail is not None
        assert detail.filename == "x.md"
        assert detail.raw_markdown is not None
        assert "# Tool Request: x" in detail.raw_markdown

    def test_missing_id_returns_none(self, db_session: Session):
        assert row_detail(db_session, 999999) is None
