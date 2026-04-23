"""Tests for core/ingest/catalog.py — TOOL-CATALOG.md → DB ingest."""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import pytest

from core.db.base import Base
from core.db import models  # noqa: F401 — register on Base.metadata
from core.db.models import Pack, Tool
from core.ingest import catalog


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=True)
    s = factory()
    try:
        yield s
    finally:
        s.close()


def test_parse_mcp_section_basic():
    body = (
        "| Name | Tools | Status | Agent | What it does | Invoke |\n"
        "|------|-------|--------|-------|--------------|--------|\n"
        "| Firefox DevTools | 24 | loaded | All | Headless browser | `firefox_*` |\n"
        "| Stripe | 28 | loaded | Alfred | Payments | `stripe_*` |\n"
    )
    rows = list(catalog.parse_mcp_section(body))
    assert len(rows) == 2
    assert rows[0].name == "Firefox DevTools"
    assert rows[0].slug == "firefox-devtools-pack"
    assert rows[0].tool_type == "mcp"
    assert rows[0].install_method == "mcp-server"
    assert rows[0].is_active is True  # "loaded"
    assert rows[0].pack_slug == "firefox-devtools"
    assert rows[0].pack_transport == "stdio"


def test_parse_mcp_section_dormant_status():
    body = (
        "| Name | Tools | Status | Agent | What it does | Invoke |\n"
        "|---|---|---|---|---|---|\n"
        "| SomeTool | 5 | dormant | Alfred | descr | `x_*` |\n"
    )
    rows = list(catalog.parse_mcp_section(body))
    assert rows[0].is_active is False


def test_parse_cli_section_not_installed():
    body = (
        "| Tool | What it does | Install | Why consider |\n"
        "|------|--------------|---------|--------------|\n"
        "| ripgrep (rg) | Fast regex search | `apt install ripgrep` | faster |\n"
        "| csvkit | CSV processing | `pip3 install --user csvkit` | handy |\n"
    )
    rows = list(catalog.parse_cli_section(body, installed=False))
    assert len(rows) == 2
    assert rows[0].name == "ripgrep (rg)"
    assert rows[0].slug == "ripgrep-rg"
    assert rows[0].tool_type == "cli"
    assert rows[0].install_method == "apt"
    assert rows[0].is_active is False
    assert rows[1].install_method == "pip-user"


def test_parse_cli_section_installed_four_col():
    body = (
        "| Tool | Version | What it does | Cost |\n"
        "|------|---------|--------------|------|\n"
        "| jq | 1.7 | JSON processor | free |\n"
    )
    rows = list(catalog.parse_cli_section(body, installed=True))
    assert len(rows) == 1
    assert rows[0].slug == "jq"
    assert rows[0].is_active is True
    assert rows[0].description == "JSON processor"


def test_parse_cli_section_installed_three_col():
    body = (
        "| Tool | What it does | Cost |\n"
        "|------|--------------|------|\n"
        "| chromium-browser | Headless Chrome | free |\n"
    )
    rows = list(catalog.parse_cli_section(body, installed=True))
    assert len(rows) == 1
    assert rows[0].description == "Headless Chrome"


def test_parse_paid_services_section():
    body = (
        "| Service | Monthly Cost | Used By | What for |\n"
        "|---------|-------------|---------|----------|\n"
        "| Anthropic (Claude) | usage-based | All agents | LLM backbone |\n"
        "| Brave Search | $5/mo | Bridge | Web search |\n"
    )
    rows = list(catalog.parse_paid_services_section(body))
    assert len(rows) == 2
    assert rows[0].tool_type == "http"
    assert rows[0].slug == "anthropic-claude-http"
    assert rows[0].category == "cost:usage-based"
    assert rows[1].category == "cost:$5/mo"


def test_infer_install_method():
    assert catalog._infer_install_method("apt install ripgrep") == "apt"
    assert catalog._infer_install_method("pip3 install --user csvkit") == "pip-user"
    assert catalog._infer_install_method("npx -y @some/package") == "npx-mcp"
    assert catalog._infer_install_method("npm install -g tool") == "npm-global"
    assert catalog._infer_install_method("binary to ~/bin") == "binary"
    assert catalog._infer_install_method("requires setup") is None
    assert catalog._infer_install_method("") is None


def test_ingest_catalog_missing_source(session, tmp_path):
    missing = tmp_path / "nope.md"
    stats = catalog.ingest_catalog(missing, session)
    assert stats.tools_created == 0
    assert any("not found" in err[1] for err in stats.errors)


def test_ingest_catalog_full_flow(session, tmp_path):
    source = tmp_path / "catalog.md"
    source.write_text(
        "# Tool Catalog\n\n"
        "## MCP Servers\n\n"
        "| Name | Tools | Status | Agent | What it does | Invoke |\n"
        "|---|---|---|---|---|---|\n"
        "| Firefox DevTools | 24 | loaded | All | Browser automation | `firefox_*` |\n\n"
        "## CLI Tools — NOT Installed\n\n"
        "| Tool | What it does | Install | Why consider |\n"
        "|---|---|---|---|\n"
        "| ripgrep | Fast search | `apt install ripgrep` | speed |\n\n"
        "## Paid Services\n\n"
        "| Service | Monthly Cost | Used By | What for |\n"
        "|---|---|---|---|\n"
        "| Anthropic | usage-based | All | LLM |\n",
        encoding="utf-8",
    )
    stats = catalog.ingest_catalog(source, session)
    assert stats.tools_created == 3  # one mcp-pack, one cli, one http
    assert stats.packs_created == 1
    tools = session.query(Tool).all()
    types = {t.tool_type for t in tools}
    assert types == {"mcp", "cli", "http"}
    # Pack was created and linked
    pack = session.query(Pack).filter_by(slug="firefox-devtools").one()
    mcp_tool = next(t for t in tools if t.tool_type == "mcp")
    assert mcp_tool.pack_id == pack.id


def test_ingest_catalog_idempotent(session, tmp_path):
    source = tmp_path / "catalog.md"
    source.write_text(
        "## MCP Servers\n\n"
        "| Name | Tools | Status | Agent | What it does | Invoke |\n"
        "|---|---|---|---|---|---|\n"
        "| Firefox DevTools | 24 | loaded | All | descr | `firefox_*` |\n",
        encoding="utf-8",
    )
    first = catalog.ingest_catalog(source, session)
    assert first.tools_created == 1
    assert first.packs_created == 1
    second = catalog.ingest_catalog(source, session)
    assert second.tools_created == 0
    assert second.packs_created == 0
    assert second.tools_updated == 1
    # No row duplication
    assert session.query(Tool).count() == 1
    assert session.query(Pack).count() == 1


def test_ingest_catalog_preserves_operator_lifecycle_fields(session, tmp_path):
    source = tmp_path / "catalog.md"
    source.write_text(
        "## CLI Tools — Installed\n\n"
        "| Tool | Version | What it does | Cost |\n"
        "|---|---|---|---|\n"
        "| ripgrep | 14.0 | Fast regex | free |\n",
        encoding="utf-8",
    )
    catalog.ingest_catalog(source, session)
    tool = session.query(Tool).filter_by(slug="ripgrep").one()
    assert tool.is_active is True  # installed section → active
    # Operator manually marks it dormant
    tool.is_active = False
    session.commit()
    # Re-ingest should NOT clobber the operator-set flag
    catalog.ingest_catalog(source, session)
    session.refresh(tool)
    assert tool.is_active is False


def test_ingest_real_legacy_source(session):
    """Smoke test against the actual _legacy TOOL-CATALOG.md.

    Guards against parser drift if the source file's structure changes.
    Asserts loose shape invariants, not exact counts.
    """
    from core.config import get_settings

    source = (
        get_settings().project_root / "_legacy" / "toolconcierge" / "TOOL-CATALOG.md"
    )
    if not source.exists():
        pytest.skip("legacy catalog not present in this checkout")
    stats = catalog.ingest_catalog(source, session)
    assert stats.tools_created > 0, "no tools parsed from real catalog"
    tools = session.query(Tool).all()
    types = {t.tool_type for t in tools}
    # All three peer categories represented
    assert "mcp" in types
    assert "cli" in types
    assert "http" in types
