"""Parse TOOL-CATALOG.md and upsert catalog entries.

Ingests three peer categories per blueprint-v2 §Five Core Capabilities
item #1:

- MCP Servers → Pack + pack-representative Tool row (`tool_type=mcp`)
- CLI Tools → one Tool per row (`tool_type=cli`), Installed vs
  Not-Installed maps to `is_active` True/False
- Paid Services → one Tool per row (`tool_type=http`)

Skills as a fourth peer category are Fix Day 2 work (separate ingest
path at `core/ingest/skills.py`, not this module).

Idempotent: upsert by slug. Descriptive fields (name, description,
tool_type, install_method) are refreshed from source. Operator-managed
lifecycle fields (`is_active`, `is_in_manifest`) are preserved on
existing rows so repeated ingest doesn't clobber hand-set state —
they're seeded from source only on first insert.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

from sqlalchemy.orm import Session

from core.db.models import Pack, Tool
from core.ingest.tool_requests import slugify


@dataclass
class CatalogRow:
    name: str
    slug: str
    tool_type: str
    description: str | None = None
    install_method: str | None = None
    category: str | None = None
    is_active: bool = True
    is_in_manifest: bool = True
    pack_slug: str | None = None
    pack_name: str | None = None
    pack_transport: str | None = None
    pack_description: str | None = None


@dataclass
class IngestStats:
    packs_created: int = 0
    packs_updated: int = 0
    tools_created: int = 0
    tools_updated: int = 0
    skipped: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)


_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_TABLE_SEP_RE = re.compile(r"^[\s|:\-]+$")


def _iter_table_rows(body: str) -> Iterator[list[str]]:
    """Yield data-row cell arrays from all markdown tables in `body`.

    Skips header rows and separator rows. Multiple tables concatenate;
    the caller discriminates by cell count or sub-header context.
    """
    seen_separator = False
    for raw in body.splitlines():
        line = raw.strip()
        if not (line.startswith("|") and line.endswith("|")):
            seen_separator = False  # table boundary
            continue
        inner = line.strip("|")
        if _TABLE_SEP_RE.match(inner):
            seen_separator = True
            continue
        if not seen_separator:
            continue  # header row
        yield [c.strip() for c in inner.split("|")]


def parse_mcp_section(body: str) -> Iterable[CatalogRow]:
    """| Name | Tools | Status | Agent | What it does | Invoke |"""
    for cells in _iter_table_rows(body):
        if len(cells) != 6:
            continue
        name, _count, status, _agent, what, _invoke = cells
        if not name:
            continue
        pack_slug = slugify(name)
        yield CatalogRow(
            name=name,
            slug=f"{pack_slug}-pack",
            tool_type="mcp",
            description=what or None,
            install_method="mcp-server",
            is_active=(status.lower() == "loaded"),
            is_in_manifest=True,
            pack_slug=pack_slug,
            pack_name=name,
            pack_transport="stdio",
            pack_description=what or None,
        )


def parse_cli_section(body: str, *, installed: bool) -> Iterable[CatalogRow]:
    """CLI tables. Shapes vary (3 or 4 cols) across sub-sections.

    Installed sub-sections: | Tool | Version | What it does | Cost |
    (Browsers is 3-col: | Tool | What it does | Cost |)
    Not-Installed: | Tool | What it does | Install | Why consider |
    """
    for cells in _iter_table_rows(body):
        if len(cells) < 3:
            continue
        name = cells[0]
        if not name or name.startswith("("):
            continue
        if installed:
            description = cells[2] if len(cells) >= 4 else cells[1]
            install_method = None  # installed-already; path unknown from this source
        else:
            description = cells[1]
            install_method = _infer_install_method(cells[2]) if len(cells) >= 3 else None
        yield CatalogRow(
            name=name,
            slug=slugify(name),
            tool_type="cli",
            description=description or None,
            install_method=install_method,
            is_active=installed,
            is_in_manifest=True,
        )


def parse_paid_services_section(body: str) -> Iterable[CatalogRow]:
    """| Service | Monthly Cost | Used By | What for |"""
    for cells in _iter_table_rows(body):
        if len(cells) != 4:
            continue
        name, cost, _used_by, what_for = cells
        if not name:
            continue
        yield CatalogRow(
            name=name,
            slug=f"{slugify(name)}-http",
            tool_type="http",
            description=what_for or None,
            install_method=None,
            category=f"cost:{cost}" if cost else None,
            is_active=True,
            is_in_manifest=True,
        )


_INSTALL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"pip.*--user", re.IGNORECASE), "pip-user"),
    (re.compile(r"\bapt(-get)?\b", re.IGNORECASE), "apt"),
    (re.compile(r"\bnpx\b", re.IGNORECASE), "npx-mcp"),
    (re.compile(r"\bnpm\b.*(\s-g\b|\bglobal\b)", re.IGNORECASE), "npm-global"),
    (re.compile(r"\bbinary\b", re.IGNORECASE), "binary"),
]


def _infer_install_method(raw: str) -> str | None:
    if not raw:
        return None
    for pattern, method in _INSTALL_PATTERNS:
        if pattern.search(raw):
            return method
    return None


def _split_sections(text: str) -> dict[str, str]:
    """Split by H2 headers → {title: body}. Later-keyed wins on duplicates."""
    positions = [(m.start(), m.group(1).strip(), m.end()) for m in _H2_RE.finditer(text)]
    out: dict[str, str] = {}
    for i, (_, title, body_start) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        out[title] = text[body_start:end]
    return out


def iter_catalog_rows(source: Path) -> Iterator[CatalogRow]:
    text = source.read_text(encoding="utf-8")
    for title, body in _split_sections(text).items():
        title_lower = title.lower()
        if "mcp servers" in title_lower:
            yield from parse_mcp_section(body)
        elif "cli tools" in title_lower:
            installed = "not installed" not in title_lower
            yield from parse_cli_section(body, installed=installed)
        elif "paid services" in title_lower:
            yield from parse_paid_services_section(body)


def ingest_catalog(source: Path, session: Session) -> IngestStats:
    """Read `source`, upsert packs + tools, return stats.

    Ordering: packs are flushed before their tools so pack.id is
    available for the tool.pack_id FK. Per-source dedup catches
    same-slug duplicates in a single run; commit-time IntegrityErrors
    would indicate a cross-source collision not covered here.
    """
    stats = IngestStats()
    if not source.exists():
        stats.errors.append((str(source), "source file not found"))
        return stats

    seen_tool_slugs: set[str] = set()
    pack_cache: dict[str, Pack] = {}

    for row in iter_catalog_rows(source):
        if row.slug in seen_tool_slugs:
            stats.skipped += 1
            stats.errors.append((row.slug, "duplicate slug in source"))
            continue
        seen_tool_slugs.add(row.slug)

        pack_id = None
        if row.pack_slug is not None:
            pack = pack_cache.get(row.pack_slug)
            if pack is None:
                pack = session.query(Pack).filter_by(slug=row.pack_slug).one_or_none()
                if pack is None:
                    pack = Pack(
                        slug=row.pack_slug,
                        name=row.pack_name or row.pack_slug,
                        description=row.pack_description,
                        transport=row.pack_transport,
                    )
                    session.add(pack)
                    session.flush()
                    stats.packs_created += 1
                else:
                    changed = False
                    if row.pack_description and pack.description != row.pack_description:
                        pack.description = row.pack_description
                        changed = True
                    if row.pack_transport and pack.transport != row.pack_transport:
                        pack.transport = row.pack_transport
                        changed = True
                    if changed:
                        stats.packs_updated += 1
                pack_cache[row.pack_slug] = pack
            pack_id = pack.id

        existing = session.query(Tool).filter_by(slug=row.slug).one_or_none()
        if existing is None:
            session.add(
                Tool(
                    slug=row.slug,
                    name=row.name,
                    description=row.description,
                    tool_type=row.tool_type,
                    category=row.category,
                    install_method=row.install_method,
                    is_in_manifest=row.is_in_manifest,
                    is_active=row.is_active,
                    pack_id=pack_id,
                )
            )
            stats.tools_created += 1
        else:
            existing.name = row.name
            existing.description = row.description
            existing.tool_type = row.tool_type
            if existing.category is None and row.category is not None:
                existing.category = row.category
            if existing.install_method is None and row.install_method is not None:
                existing.install_method = row.install_method
            if existing.pack_id is None and pack_id is not None:
                existing.pack_id = pack_id
            stats.tools_updated += 1

    session.commit()
    return stats


def main() -> None:
    """Usage: python -m core.ingest.catalog [source_path]

    Defaults to the legacy TOOL-CATALOG.md under project_root/_legacy.
    """
    import sys

    from core.config import get_settings
    from core.db.session import get_session_factory

    settings = get_settings()
    if len(sys.argv) > 1:
        source = Path(sys.argv[1])
    else:
        source = settings.project_root / "_legacy" / "toolconcierge" / "TOOL-CATALOG.md"

    session = get_session_factory()()
    try:
        stats = ingest_catalog(source, session)
    finally:
        session.close()

    print(f"Ingested from: {source}")
    print(f"  Packs: +{stats.packs_created} created, ~{stats.packs_updated} updated")
    print(f"  Tools: +{stats.tools_created} created, ~{stats.tools_updated} updated")
    print(f"  Skipped: {stats.skipped}")
    if stats.errors:
        print(f"  Errors ({len(stats.errors)}):")
        for slug, err in stats.errors:
            print(f"    {slug}: {err}")


if __name__ == "__main__":
    main()
