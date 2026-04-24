"""Tests for core/ingest/skills.py — skills → DB ingest.

Skills are the fourth peer catalog category per blueprint-v2 §Five
Core Capabilities item #1 (DECISIONS `[2026-04-23]` — Skills as fourth
catalog category with full peer status).

Fixture synthesizes a realistic `<skills_root>/{public,user,examples}`
layout under `tmp_path`; the real-source smoke test runs only when
`Settings.skills_root` is actually present on the host.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from core.db.base import Base
from core.db import models  # noqa: F401 — register on Base.metadata
from core.db.models import Tool
from core.ingest import skills


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


def _write_skill(root: Path, subdir: str, skill_dir: str, frontmatter: str) -> Path:
    path = root / subdir / skill_dir / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter, encoding="utf-8")
    return path


@pytest.fixture
def skills_root(tmp_path: Path) -> Path:
    """Synthetic `public/user/examples` layout with seed skills in each."""
    root = tmp_path / "skills"
    _write_skill(
        root, "public", "update-config",
        "---\n"
        "name: update-config\n"
        "description: Configure the Claude Code harness via settings.json.\n"
        "---\n\n"
        "# Update Config\n"
    )
    _write_skill(
        root, "public", "simplify",
        "---\n"
        "name: simplify\n"
        "description: Review changed code for reuse and quality.\n"
        "---\n"
    )
    _write_skill(
        root, "public", "loop",
        "---\n"
        "name: loop\n"
        "description: Run a prompt on a recurring interval.\n"
        "---\n"
    )
    _write_skill(
        root, "user", "my-custom-skill",
        "---\n"
        "name: my-custom-skill\n"
        "description: Operator's local scratch skill.\n"
        "---\n"
    )
    _write_skill(
        root, "examples", "demo-skill",
        "---\n"
        "name: demo-skill\n"
        "description: Example skill used in docs.\n"
        "---\n"
    )
    return root


def test_parse_skill_frontmatter_minimal():
    text = "---\nname: foo\ndescription: A test skill.\n---\n\n# Body\n"
    fm = skills.parse_skill_frontmatter(text)
    assert fm == {"name": "foo", "description": "A test skill."}


def test_parse_skill_frontmatter_none_when_missing():
    assert skills.parse_skill_frontmatter("No frontmatter here\n") is None


def test_parse_skill_frontmatter_continuation_line():
    text = (
        "---\n"
        "name: big-skill\n"
        "description: A multi-line description that\n"
        "  continues onto the next line.\n"
        "---\n"
    )
    fm = skills.parse_skill_frontmatter(text)
    assert fm is not None
    assert fm["description"] == (
        "A multi-line description that continues onto the next line."
    )


def test_parse_skill_frontmatter_tolerates_leading_bom_and_whitespace():
    text = "﻿\n\n---\nname: foo\n---\n"
    fm = skills.parse_skill_frontmatter(text)
    assert fm == {"name": "foo"}


def test_iter_skill_rows_walks_three_subdirs(skills_root: Path):
    rows = list(skills.iter_skill_rows(skills_root))
    slugs = [r.slug for r in rows]
    subdirs_seen = {r.source_subdir for r in rows}
    # All five seed skills present
    assert set(slugs) == {
        "update-config", "simplify", "loop",
        "my-custom-skill", "demo-skill",
    }
    assert subdirs_seen == {"public", "user", "examples"}


def test_iter_skill_rows_deterministic_order(skills_root: Path):
    rows = list(skills.iter_skill_rows(skills_root))
    # public comes before user comes before examples
    first_user_idx = next(
        i for i, r in enumerate(rows) if r.source_subdir == "user"
    )
    first_examples_idx = next(
        i for i, r in enumerate(rows) if r.source_subdir == "examples"
    )
    # All public rows precede the first user row
    assert all(
        rows[i].source_subdir == "public" for i in range(first_user_idx)
    )
    # All user rows precede the first examples row
    assert all(
        rows[i].source_subdir in ("public", "user")
        for i in range(first_examples_idx)
    )


def test_iter_skill_rows_skips_missing_subdirs(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    # Only public present
    _write_skill(
        tmp_path, "public", "only-skill",
        "---\nname: only-skill\n---\n"
    )
    with caplog.at_level(logging.WARNING, logger="concierge.ingest.skills"):
        rows = list(skills.iter_skill_rows(tmp_path))
    assert len(rows) == 1
    assert any("subdir_missing" in rec.message for rec in caplog.records)
    assert any("subdir=user" in rec.message for rec in caplog.records)
    assert any("subdir=examples" in rec.message for rec in caplog.records)


def test_iter_skill_rows_skips_missing_name(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    _write_skill(
        tmp_path, "public", "nameless",
        "---\ndescription: no name at all\n---\n"
    )
    with caplog.at_level(logging.WARNING, logger="concierge.ingest.skills"):
        rows = list(skills.iter_skill_rows(tmp_path))
    assert rows == []
    assert any("missing_name" in rec.message for rec in caplog.records)


def test_iter_skill_rows_skips_no_frontmatter(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    _write_skill(tmp_path, "public", "bare", "# no frontmatter\nbody only\n")
    with caplog.at_level(logging.WARNING, logger="concierge.ingest.skills"):
        rows = list(skills.iter_skill_rows(tmp_path))
    assert rows == []
    assert any("no_frontmatter" in rec.message for rec in caplog.records)


def test_ingest_skills_full_flow(skills_root: Path, session: Session):
    stats = skills.ingest_skills(skills_root, session)
    assert stats.tools_created == 5
    assert stats.tools_updated == 0
    assert stats.skipped == 0
    assert stats.subdirs_walked == 3
    assert stats.subdirs_missing == 0

    rows = session.query(Tool).filter_by(tool_type="skill").all()
    assert len(rows) == 5
    for r in rows:
        assert r.ambient_loading is True
        assert r.path is not None
        assert r.path.endswith("/SKILL.md")
        assert r.is_in_manifest is True
        assert r.is_active is True
        assert r.lifecycle_state == "discovered"  # server_default


def test_ingest_skills_missing_root_returns_zero(
    tmp_path: Path, session: Session, caplog: pytest.LogCaptureFixture
):
    missing = tmp_path / "nowhere"
    with caplog.at_level(logging.WARNING, logger="concierge.ingest.skills"):
        stats = skills.ingest_skills(missing, session)
    assert stats.tools_created == 0
    assert stats.subdirs_missing == len(skills.SUBDIRS)
    assert any("root_missing" in rec.message for rec in caplog.records)
    assert session.query(Tool).count() == 0


def test_ingest_skills_idempotent(skills_root: Path, session: Session):
    first = skills.ingest_skills(skills_root, session)
    assert first.tools_created == 5
    second = skills.ingest_skills(skills_root, session)
    assert second.tools_created == 0
    assert second.tools_updated == 5
    assert session.query(Tool).count() == 5


def test_ingest_skills_slug_collision_first_seen_wins(
    tmp_path: Path, session: Session, caplog: pytest.LogCaptureFixture
):
    _write_skill(
        tmp_path, "public", "shared-name",
        "---\nname: shared-name\ndescription: public version\n---\n"
    )
    _write_skill(
        tmp_path, "user", "shared-name",
        "---\nname: shared-name\ndescription: user override\n---\n"
    )
    _write_skill(
        tmp_path, "examples", "shared-name",
        "---\nname: shared-name\ndescription: example version\n---\n"
    )
    with caplog.at_level(logging.WARNING, logger="concierge.ingest.skills"):
        stats = skills.ingest_skills(tmp_path, session)

    assert stats.tools_created == 1
    assert stats.skipped == 2
    # Public wins (walk order: public → user → examples)
    tool = session.query(Tool).filter_by(slug="shared-name").one()
    assert tool.description == "public version"
    assert "/public/" in tool.path

    collision_msgs = [
        r.message for r in caplog.records if "slug_collision" in r.message
    ]
    assert len(collision_msgs) == 2


def test_ingest_skills_preserves_operator_lifecycle_on_rerun(
    skills_root: Path, session: Session
):
    skills.ingest_skills(skills_root, session)
    tool = session.query(Tool).filter_by(slug="update-config").one()
    # Operator marks it retired via direct DB edit
    tool.is_active = False
    tool.lifecycle_state = "retired"
    session.commit()
    # Re-ingest must not clobber the retire-decision
    skills.ingest_skills(skills_root, session)
    session.refresh(tool)
    assert tool.is_active is False
    assert tool.lifecycle_state == "retired"
    # But descriptive fields did refresh
    assert tool.tool_type == "skill"


def test_ingest_skills_real_source_smoke(session: Session):
    """Smoke test against `Settings.skills_root` if present on this host.

    Claude.ai-hosted sessions have `/mnt/skills/` mounted and should
    populate ≥1 row. Local Claude Code CLI typically doesn't have this
    path — the test then `skip`s rather than failing. Operators can
    force a smoke run by setting `CONCIERGE_SKILLS_ROOT` to a directory
    that actually has the three subdirs populated.
    """
    from core.config import get_settings

    root = get_settings().skills_root
    if not (root / "public").is_dir():
        pytest.skip(f"skills_root not populated at {root} on this host")
    stats = skills.ingest_skills(root, session)
    assert stats.tools_created + stats.tools_updated >= 1, (
        f"no skills parsed from real source at {root}"
    )
    skill_rows = session.query(Tool).filter_by(tool_type="skill").all()
    assert all(r.ambient_loading is True for r in skill_rows)
    assert all(r.path and r.path.endswith("/SKILL.md") for r in skill_rows)
