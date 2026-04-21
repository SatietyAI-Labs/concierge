from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from core.db.base import Base
from core.db.models import Request
from core.ingest import tool_requests as ti


def test_parse_filename_valid():
    dt, slug = ti.parse_filename("2026-04-13-2018-csvkit-for-csv-analysis.md")
    assert dt == datetime(2026, 4, 13, 20, 18)
    assert slug == "csvkit-for-csv-analysis"


def test_parse_filename_invalid_returns_none():
    dt, slug = ti.parse_filename("random-garbage.md")
    assert dt is None
    assert slug is None


def test_parse_status_valid():
    assert ti.parse_status("status: pending\n# Heading") == "pending"
    assert ti.parse_status("status: installed\n# Heading") == "installed"


def test_parse_status_missing():
    assert ti.parse_status("# Heading only, no status") is None


def test_parse_sections_full():
    text = (
        "status: pending\n\n"
        "# Tool Request: ripgrep\n\n"
        "## Request\n\n"
        "- **Task context:** searching a huge repo\n"
        "- **Tool suggested:** ripgrep\n"
        "- **Category:** search\n"
        "- **Discovered:** false\n\n"
        "## Recommendation\n\n"
        "- **Confidence:** high\n"
    )
    sections = ti.parse_sections(text)
    assert set(sections.keys()) == {"request", "recommendation"}
    assert sections["request"]["task_context"] == "searching a huge repo"
    assert sections["request"]["tool_suggested"] == "ripgrep"
    assert sections["request"]["category"] == "search"
    assert sections["request"]["discovered"] is False
    assert sections["recommendation"]["confidence"] == "high"


def test_parse_sections_empty_fields():
    text = (
        "## Approval\n\n"
        "- **Decision:** \n"
        "- **Conditions:** \n"
        "- **Date:** \n"
    )
    sections = ti.parse_sections(text)
    assert sections["approval"]["decision"] == ""
    assert sections["approval"]["conditions"] == ""
    assert sections["approval"]["date"] == ""


def test_parse_request_file_end_to_end(tmp_path: Path):
    content = (
        "status: approved\n\n"
        "# Tool Request: ripgrep (rg)\n\n"
        "## Request\n\n"
        "- **Task context:** big repo search\n"
        "- **Tool suggested:** ripgrep (rg)\n"
        "- **Category:** search\n\n"
        "## Recommendation\n\n"
        "- **Confidence:** high\n"
    )
    path = tmp_path / "2026-04-13-2028-ripgrep-for-codebase-search.md"
    path.write_text(content)

    parsed = ti.parse_request_file(path, "resolved")
    assert parsed.filename == path.name
    assert parsed.folder == "resolved"
    assert parsed.status == "approved"
    assert parsed.tool_name == "ripgrep (rg)"
    assert parsed.tool_slug == "ripgrep"
    assert parsed.category == "search"
    assert parsed.confidence == "high"
    assert parsed.is_discovered is False
    assert parsed.created_at == datetime(2026, 4, 13, 20, 28)


def test_parse_rejects_missing_status(tmp_path: Path):
    content = "# Tool Request: foo\n\n## Request\n- **Category:** x\n"
    path = tmp_path / "2026-04-13-1100-foo.md"
    path.write_text(content)
    with pytest.raises(ti.ParseError, match="missing status"):
        ti.parse_request_file(path, "pending")


def test_parse_rejects_invalid_status(tmp_path: Path):
    content = "status: zombie\n\n# Tool Request: foo\n"
    path = tmp_path / "2026-04-13-1100-foo.md"
    path.write_text(content)
    with pytest.raises(ti.ParseError, match="invalid status"):
        ti.parse_request_file(path, "pending")


def test_parse_rejects_missing_h1(tmp_path: Path):
    content = "status: pending\n\nsome other markdown\n"
    path = tmp_path / "2026-04-13-1100-foo.md"
    path.write_text(content)
    with pytest.raises(ti.ParseError, match="missing '# Tool Request:' heading"):
        ti.parse_request_file(path, "pending")


def test_ingest_writes_to_db(tmp_path: Path, db_session: Session):
    pending = tmp_path / "pending"
    pending.mkdir()
    (pending / "2026-04-13-1100-foo.md").write_text(
        "status: pending\n\n"
        "# Tool Request: foo\n\n"
        "## Request\n- **Category:** cli\n"
    )
    stats = ti.ingest_directory(tmp_path, db_session)
    assert stats.ingested == 1
    assert stats.updated == 0
    assert stats.errors == []

    row = db_session.query(Request).filter_by(filename="2026-04-13-1100-foo.md").one()
    assert row.folder == "pending"
    assert row.status == "pending"
    assert row.tool_name == "foo"
    assert row.tool_slug == "foo"
    assert row.category == "cli"
    assert row.parsed_data["request"]["category"] == "cli"


def test_ingest_is_idempotent(tmp_path: Path, db_session: Session):
    pending = tmp_path / "pending"
    pending.mkdir()
    (pending / "2026-04-13-1100-foo.md").write_text(
        "status: pending\n\n# Tool Request: foo\n"
    )

    first = ti.ingest_directory(tmp_path, db_session)
    second = ti.ingest_directory(tmp_path, db_session)

    assert first.ingested == 1
    assert first.updated == 0
    assert second.ingested == 0
    assert second.updated == 1
    assert db_session.query(Request).count() == 1


def test_ingest_resolves_duplicate_filename_across_folders(
    tmp_path: Path, db_session: Session
):
    (tmp_path / "pending").mkdir()
    (tmp_path / "resolved").mkdir()
    (tmp_path / "pending" / "2026-04-13-1100-x.md").write_text(
        "status: pending\n\n# Tool Request: x\n"
    )
    (tmp_path / "resolved" / "2026-04-13-1100-x.md").write_text(
        "status: installed\n\n# Tool Request: x\n"
    )

    stats = ti.ingest_directory(tmp_path, db_session)
    row = db_session.query(Request).filter_by(filename="2026-04-13-1100-x.md").one()
    assert row.folder == "resolved"
    assert row.status == "installed"
    assert stats.ingested == 1
    assert stats.updated == 1


def test_ingest_collects_errors_for_malformed_files(
    tmp_path: Path, db_session: Session
):
    pending = tmp_path / "pending"
    pending.mkdir()
    (pending / "2026-04-13-1100-bad.md").write_text("no status line here\n")

    stats = ti.ingest_directory(tmp_path, db_session)
    assert stats.ingested == 0
    assert len(stats.errors) == 1
    assert "missing status" in stats.errors[0][1]
    assert db_session.query(Request).count() == 0


def test_ingest_handles_missing_root_gracefully(
    tmp_path: Path, db_session: Session
):
    nonexistent = tmp_path / "does-not-exist"
    stats = ti.ingest_directory(nonexistent, db_session)
    assert stats.ingested == 0
    assert stats.updated == 0
    assert stats.errors == []


def test_ingest_real_legacy_corpus(db_session: Session):
    from core.config import get_settings

    root = get_settings().lifecycle_root
    if not root.exists():
        pytest.skip(f"legacy lifecycle root unavailable: {root}")

    stats = ti.ingest_directory(root, db_session)
    assert stats.errors == [], f"unexpected parse errors: {stats.errors}"

    rows = db_session.query(Request).all()
    assert len(rows) >= 4, f"expected >=4 ingested rows, got {len(rows)}"

    statuses = {r.status for r in rows}
    assert statuses <= ti.VALID_STATUSES

    folders = {r.folder for r in rows}
    assert folders <= set(ti.FOLDER_ORDER)

    for r in rows:
        assert r.raw_markdown, f"raw_markdown empty for {r.filename}"
        assert isinstance(r.parsed_data, dict)
        assert r.tool_slug, f"tool_slug empty for {r.filename}"


def test_ingest_via_production_session_factory_on_disk(tmp_path: Path):
    """Exercise the real session factory + on-disk SQLite to catch
    autoflush/identity-map bugs that in-memory fixtures hide."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.config import Settings
    from core.db.session import make_engine

    db_file = tmp_path / "ingest-live.db"
    settings = Settings(database_path=db_file)
    engine = make_engine(settings)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=True)

    pending = tmp_path / "pending"
    resolved = tmp_path / "resolved"
    pending.mkdir()
    resolved.mkdir()
    (pending / "2026-04-13-1100-x.md").write_text(
        "status: pending\n\n# Tool Request: x\n"
    )
    (resolved / "2026-04-13-1100-x.md").write_text(
        "status: installed\n\n# Tool Request: x\n"
    )

    session = factory()
    try:
        stats = ti.ingest_directory(tmp_path, session)
    finally:
        session.close()

    assert stats.errors == []
    verify = factory()
    try:
        rows = verify.query(Request).all()
        assert len(rows) == 1
        assert rows[0].folder == "resolved"
        assert rows[0].status == "installed"
    finally:
        verify.close()
