"""Walk the Claude skills layout (`<skills_root>/{public,user,examples}`)
and register each SKILL.md as a catalog entry with `tool_type='skill'`.

Skills are the fourth peer category per blueprint-v2 §Five Core
Capabilities item #1. Before this ingest they were invisible to
Concierge — sitting in `/mnt/skills/` directories, loaded on-demand by
Claude when the SKILL.md's trigger conditions matched, with no
systemic memory, lifecycle, or recommendation-engine awareness. This
module registers them alongside MCP / CLI / HTTP tools so the same
promotion/demotion, usage telemetry, and recommendation logic applies.

**Source layout** — each subtree holds one or more
`<skill-name>/SKILL.md` files. Frontmatter is YAML between `---`
delimiters. `name` is required; `description` is recommended; any other
fields are ignored (not load-bearing in this ingest). Per-skill slug is
`slugify(name)`.

**Idempotency** — upsert by slug. Descriptive fields are refreshed from
source on every run; operator-managed lifecycle fields
(`is_active`, `is_in_manifest`, `lifecycle_state`) are preserved on
existing rows so repeated ingest doesn't clobber hand-set state. The
only skill-specific fields set on upsert are `path` and
`ambient_loading=True`.

**Collision handling** — when the same slug appears in more than one
subtree (e.g. a `public` skill and a user-supplied `user` skill with
identical frontmatter name), the first-seen wins. Walk order is
deterministic: `public` → `user` → `examples`. Subsequent collisions
log a WARNING naming both paths and are skipped.

**Missing root** — when `skills_root` (or any of its three subdirs)
doesn't exist on the host, the walk logs a WARNING and returns
zero-ingested. First boot on a fresh Claude Code CLI clone (where
`/mnt/skills/` isn't mounted) therefore doesn't crash; the operator
either points `CONCIERGE_SKILLS_ROOT` at a real skills directory or
lives without skill-category rows until the next deploy env has
them mounted.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

from sqlalchemy.orm import Session

from core.db.models import Tool
from core.ingest.tool_requests import slugify


log = logging.getLogger("concierge.ingest.skills")


SUBDIRS: tuple[str, ...] = ("public", "user", "examples")
"""Deterministic walk order. First-seen-wins on slug collisions."""


_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(?P<body>.*?)\n---\s*(\n|$)", re.DOTALL
)
_FM_FIELD_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(?P<value>.*)$")


@dataclass
class SkillRow:
    name: str
    slug: str
    description: str | None
    path: str
    source_subdir: str


@dataclass
class SkillIngestStats:
    tools_created: int = 0
    tools_updated: int = 0
    skipped: int = 0
    subdirs_walked: int = 0
    subdirs_missing: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)


def parse_skill_frontmatter(text: str) -> dict[str, str] | None:
    """Return a dict of frontmatter fields or None if no frontmatter block.

    Values after the `key:` are stripped of surrounding whitespace. Only
    single-line scalar values are supported — anything fancier (lists,
    multi-line, block scalars) falls through as the raw text, which the
    caller can choose to tolerate. Frontmatter is intentionally minimal
    here: we only need `name` and `description` today.
    """
    match = _FRONTMATTER_RE.match(text.lstrip("﻿").lstrip())
    if match is None:
        return None
    fields: dict[str, str] = {}
    current_key: str | None = None
    for raw_line in match.group("body").splitlines():
        field_match = _FM_FIELD_RE.match(raw_line)
        if field_match:
            current_key = field_match.group("key")
            fields[current_key] = field_match.group("value").strip()
        elif current_key is not None and raw_line.startswith((" ", "\t")):
            # Continuation line — fold onto prior key with single space.
            continuation = raw_line.strip()
            if continuation:
                fields[current_key] = (
                    f"{fields[current_key]} {continuation}".strip()
                )
    return fields


def iter_skill_rows(skills_root: Path) -> Iterator[SkillRow]:
    """Yield SkillRow per valid SKILL.md under `skills_root/{public,user,examples}`.

    Missing subdirs log WARN and contribute zero rows; malformed
    frontmatter logs WARN + skips (caller gets no row). Walk order is
    deterministic across subdirs (SUBDIRS) and stable within a subdir
    via `sorted(...)`.
    """
    for subdir_name in SUBDIRS:
        subdir = skills_root / subdir_name
        if not subdir.is_dir():
            log.warning(
                "skills_ingest.subdir_missing root=%s subdir=%s",
                skills_root, subdir_name,
            )
            continue
        for skill_file in sorted(subdir.rglob("SKILL.md")):
            try:
                text = skill_file.read_text(encoding="utf-8")
            except OSError as exc:
                log.warning(
                    "skills_ingest.read_failed path=%s err=%s",
                    skill_file, exc,
                )
                continue
            fm = parse_skill_frontmatter(text)
            if fm is None:
                log.warning(
                    "skills_ingest.no_frontmatter path=%s", skill_file
                )
                continue
            name = fm.get("name", "").strip()
            if not name:
                log.warning(
                    "skills_ingest.missing_name path=%s", skill_file
                )
                continue
            yield SkillRow(
                name=name,
                slug=slugify(name),
                description=fm.get("description") or None,
                path=str(skill_file.resolve()),
                source_subdir=subdir_name,
            )


def ingest_skills(
    skills_root: Path, session: Session
) -> SkillIngestStats:
    """Upsert skill rows under `skills_root` into the `tools` table.

    Returns stats reflecting what happened (created vs updated vs
    skipped-on-collision, plus missing-subdir count). On missing root,
    all three subdirs are counted missing and zero rows land.
    """
    stats = SkillIngestStats()

    if not skills_root.exists():
        log.warning(
            "skills_ingest.root_missing path=%s (returning zero-ingested)",
            skills_root,
        )
        stats.subdirs_missing = len(SUBDIRS)
        return stats

    for subdir_name in SUBDIRS:
        if (skills_root / subdir_name).is_dir():
            stats.subdirs_walked += 1
        else:
            stats.subdirs_missing += 1

    seen_slugs: dict[str, str] = {}  # slug → winning path

    for row in iter_skill_rows(skills_root):
        prior = seen_slugs.get(row.slug)
        if prior is not None:
            log.warning(
                "skills_ingest.slug_collision slug=%s first=%s duplicate=%s",
                row.slug, prior, row.path,
            )
            stats.skipped += 1
            stats.errors.append(
                (row.slug, f"collision: already seen at {prior}")
            )
            continue
        seen_slugs[row.slug] = row.path

        existing = session.query(Tool).filter_by(slug=row.slug).one_or_none()
        if existing is None:
            session.add(
                Tool(
                    slug=row.slug,
                    name=row.name,
                    description=row.description,
                    tool_type="skill",
                    path=row.path,
                    ambient_loading=True,
                    is_in_manifest=True,
                    is_active=True,
                )
            )
            stats.tools_created += 1
        else:
            # Refresh descriptive fields; preserve operator lifecycle flags.
            existing.name = row.name
            existing.description = row.description
            existing.tool_type = "skill"
            existing.path = row.path
            if existing.ambient_loading is None:
                existing.ambient_loading = True
            stats.tools_updated += 1

    session.commit()
    return stats


def main() -> None:
    """Usage: python -m core.ingest.skills [skills_root]

    Defaults to `Settings.skills_root` (`/mnt/skills` unless overridden
    via `CONCIERGE_SKILLS_ROOT`).
    """
    import sys

    from core.config import get_settings
    from core.db.session import get_session_factory

    settings = get_settings()
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else settings.skills_root

    session = get_session_factory()()
    try:
        stats = ingest_skills(root, session)
    finally:
        session.close()

    print(f"Ingested skills from: {root}")
    print(f"  Subdirs walked: {stats.subdirs_walked} / missing: {stats.subdirs_missing}")
    print(f"  Skills: +{stats.tools_created} created, ~{stats.tools_updated} updated")
    print(f"  Skipped (collisions): {stats.skipped}")
    if stats.errors:
        print(f"  Errors ({len(stats.errors)}):")
        for slug, err in stats.errors:
            print(f"    {slug}: {err}")


if __name__ == "__main__":
    main()
