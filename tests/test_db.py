import sqlite3
from pathlib import Path

from sqlalchemy.orm import Session

from core.config import Settings
from core.db import models
from core.db.base import Base
from core.db.session import make_engine


def test_all_four_tables_in_metadata():
    expected = {"packs", "tools", "requests", "memory_events"}
    assert expected <= set(Base.metadata.tables.keys())


def test_pack_roundtrip(db_session: Session):
    pack = models.Pack(
        slug="firefox-devtools",
        name="Firefox DevTools",
        description="Headless browser automation",
        transport="stdio",
        status="active",
    )
    db_session.add(pack)
    db_session.commit()

    fetched = db_session.query(models.Pack).filter_by(slug="firefox-devtools").one()
    assert fetched.id is not None
    assert fetched.name == "Firefox DevTools"
    assert fetched.transport == "stdio"
    assert fetched.status == "active"
    assert fetched.created_at is not None


def test_tool_pack_relationship(db_session: Session):
    pack = models.Pack(slug="memory-mcp", name="Memory MCP", transport="stdio")
    tool = models.Tool(
        slug="memory-store",
        name="memory_store",
        description="Save a memory with tags",
        category="ai-services",
        install_method="mcp-server",
        pack=pack,
        is_in_manifest=True,
        is_active=True,
    )
    db_session.add(tool)
    db_session.commit()

    fetched_pack = db_session.query(models.Pack).filter_by(slug="memory-mcp").one()
    assert len(fetched_pack.tools) == 1
    assert fetched_pack.tools[0].slug == "memory-store"
    assert fetched_pack.tools[0].is_active is True
    assert fetched_pack.tools[0].pack_id == fetched_pack.id


def test_dormant_tool_query(db_session: Session):
    db_session.add_all(
        [
            models.Tool(slug="ripgrep", name="ripgrep", is_in_manifest=True, is_active=True),
            models.Tool(slug="csvkit", name="csvkit", is_in_manifest=True, is_active=False),
            models.Tool(slug="pandoc", name="pandoc", is_in_manifest=False, is_active=False),
        ]
    )
    db_session.commit()

    dormants = (
        db_session.query(models.Tool)
        .filter(models.Tool.is_in_manifest.is_(True), models.Tool.is_active.is_(False))
        .all()
    )
    assert [t.slug for t in dormants] == ["csvkit"]


def test_request_roundtrip_preserves_markdown_and_parsed_data(db_session: Session):
    raw = (
        "status: pending\n\n"
        "# Tool Request: csvkit\n\n"
        "## Request\n- **Task context:** Analyzing CSV export\n"
        "- **Tool suggested:** csvkit\n- **Category:** data-processing\n"
    )
    req = models.Request(
        filename="2026-04-13-2018-csvkit-for-csv-analysis.md",
        status="pending",
        folder="pending",
        tool_name="csvkit",
        tool_slug="csvkit",
        category="data-processing",
        confidence="high",
        is_discovered=False,
        raw_markdown=raw,
        parsed_data={
            "request": {
                "task_context": "Analyzing CSV export",
                "tool_suggested": "csvkit",
                "category": "data-processing",
            },
            "recommendation": {"confidence": "high"},
        },
    )
    db_session.add(req)
    db_session.commit()

    fetched = (
        db_session.query(models.Request)
        .filter_by(filename="2026-04-13-2018-csvkit-for-csv-analysis.md")
        .one()
    )
    assert fetched.raw_markdown == raw
    assert fetched.parsed_data["recommendation"]["confidence"] == "high"
    assert fetched.parsed_data["request"]["tool_suggested"] == "csvkit"


def test_memory_event_roundtrip(db_session: Session):
    evt = models.MemoryEvent(
        event_type="token_win",
        tags=["token-win", "csvkit"],
        payload={"task": "csv analysis", "tokens_saved": 380},
        source="alfred-session-123",
    )
    db_session.add(evt)
    db_session.commit()

    fetched = db_session.query(models.MemoryEvent).one()
    assert fetched.event_type == "token_win"
    assert "token-win" in fetched.tags
    assert fetched.payload["tokens_saved"] == 380
    assert fetched.source == "alfred-session-123"
    assert fetched.occurred_at is not None


def test_init_db_materializes_schema_on_disk(tmp_path: Path):
    db_file = tmp_path / "test-concierge.db"
    settings = Settings(database_path=db_file)
    engine = make_engine(settings)
    Base.metadata.create_all(engine)

    assert db_file.exists()

    conn = sqlite3.connect(str(db_file))
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    finally:
        conn.close()

    table_names = {row[0] for row in rows}
    assert {"packs", "tools", "requests", "memory_events"} <= table_names


def test_init_db_creates_indexes_on_disk(tmp_path: Path):
    db_file = tmp_path / "test-concierge-indexes.db"
    settings = Settings(database_path=db_file)
    engine = make_engine(settings)
    Base.metadata.create_all(engine)

    conn = sqlite3.connect(str(db_file))
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"
        ).fetchall()
    finally:
        conn.close()

    index_names = {row[0] for row in rows}
    assert any("packs" in n and "slug" in n for n in index_names)
    assert any("tools" in n and "slug" in n for n in index_names)
    assert any("requests" in n and "filename" in n for n in index_names)
    assert any("memory_events" in n and "occurred_at" in n for n in index_names)
