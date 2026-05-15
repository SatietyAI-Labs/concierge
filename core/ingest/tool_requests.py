"""Parse tool-request markdown files and upsert into the `requests` table.

Markdown format and lifecycle documented at
`_legacy/tool-requests/README.md`. This module implements the *ingest*
half (markdown → SQLite). The export half lands in N4.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from core.db.models import Request

FOLDER_ORDER = ("pending", "resolved", "archived")
VALID_STATUSES = frozenset(
    {"pending", "approved", "denied", "installed", "failed", "deferred"}
)

_FILENAME_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})-(?P<time>\d{4})-(?P<slug>.+)\.md$"
)
_STATUS_RE = re.compile(r"^status:\s*(\S+)", re.MULTILINE)
_H1_RE = re.compile(r"^#\s+Tool Request:\s*(.+?)\s*$", re.MULTILINE)
_FIELD_RE = re.compile(
    r"^-[ \t]+\*\*(?P<field>[^*]+?):\*\*[ \t]*(?P<value>.*)$", re.MULTILINE
)
_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


class ParseError(Exception):
    pass


@dataclass
class ParsedRequest:
    filename: str
    folder: str
    status: str
    tool_name: str
    created_at: datetime | None
    raw_markdown: str
    sections: dict[str, dict[str, Any]]
    tool_slug: str | None
    category: str | None
    confidence: str | None
    is_discovered: bool


@dataclass
class IngestStats:
    ingested: int = 0
    updated: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)


def parse_filename(filename: str) -> tuple[datetime | None, str | None]:
    """YYYY-MM-DD-HHMM-<slug>.md → (datetime, slug). Returns (None, None) on mismatch."""
    m = _FILENAME_RE.match(filename)
    if not m:
        return None, None
    try:
        dt = datetime.strptime(f"{m['date']}-{m['time']}", "%Y-%m-%d-%H%M")
    except ValueError:
        dt = None
    return dt, m["slug"]


def parse_status(text: str) -> str | None:
    m = _STATUS_RE.search(text)
    return m.group(1) if m else None


def parse_h1_tool_name(text: str) -> str | None:
    m = _H1_RE.search(text)
    return m.group(1).strip() if m else None


def parse_sections(text: str) -> dict[str, dict[str, Any]]:
    positions = [(m.start(), m.group(1).strip()) for m in _SECTION_RE.finditer(text)]
    if not positions:
        return {}
    sections: dict[str, dict[str, Any]] = {}
    for i, (start, header) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        body = text[start:end]
        key = _section_key(header)
        fields: dict[str, Any] = {}
        for fm in _FIELD_RE.finditer(body):
            field_name = _field_key(fm.group("field"))
            value = fm.group("value").strip()
            if field_name == "discovered":
                fields[field_name] = value.lower() == "true"
            else:
                fields[field_name] = value
        sections[key] = fields
    return sections


def _section_key(header: str) -> str:
    return header.strip().lower().replace(" ", "_")


def _field_key(field_name: str) -> str:
    return field_name.strip().lower().replace(" ", "_").replace("/", "_")


def slugify(name: str) -> str:
    return _SLUG_NON_ALNUM.sub("-", name.lower()).strip("-")


def _tool_name_to_slug(name: str) -> str:
    base = re.split(r"[(:]+", name, maxsplit=1)[0].strip()
    return slugify(base)


def parse_request_file(path: Path, folder: str) -> ParsedRequest:
    raw = path.read_text(encoding="utf-8")
    status = parse_status(raw)
    if status is None:
        raise ParseError(f"missing status line in {path.name}")
    if status not in VALID_STATUSES:
        raise ParseError(f"invalid status {status!r} in {path.name}")
    tool_name = parse_h1_tool_name(raw)
    if tool_name is None:
        raise ParseError(f"missing '# Tool Request:' heading in {path.name}")
    created_at, _ = parse_filename(path.name)
    sections = parse_sections(raw)
    req = sections.get("request", {})
    rec = sections.get("recommendation", {})
    confidence = (rec.get("confidence") or "").strip().lower() or None
    return ParsedRequest(
        filename=path.name,
        folder=folder,
        status=status,
        tool_name=tool_name,
        created_at=created_at,
        raw_markdown=raw,
        sections=sections,
        tool_slug=_tool_name_to_slug(tool_name),
        category=(req.get("category") or None),
        confidence=confidence,
        is_discovered=bool(req.get("discovered", False)),
    )


def ingest_directory(root: Path, session: Session) -> IngestStats:
    """Walk root/{pending,resolved,archived}/*.md; upsert into `requests`.

    Folder processing order is FOLDER_ORDER — later-stage state wins on
    duplicate filename (reflects the cron-housekeeping lifecycle direction).
    """
    stats = IngestStats()
    if not root.exists():
        return stats
    for folder in FOLDER_ORDER:
        folder_path = root / folder
        if not folder_path.exists():
            continue
        for md_file in sorted(folder_path.glob("*.md")):
            try:
                parsed = parse_request_file(md_file, folder)
            except ParseError as e:
                stats.errors.append((str(md_file), str(e)))
                continue
            _upsert_request(session, parsed, stats)
    session.commit()
    return stats


_EXPORT_SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Request",
        [
            ("Task context", "task_context"),
            ("Tool suggested", "tool_suggested"),
            ("Category", "category"),
            ("Install method", "install_method"),
            ("Discovered", "discovered"),
        ],
    ),
    # Stage 1A item 5 — worker-to-Alfred escalation section. Slotted
    # between Request and Recommendation so Alfred reads the worker
    # context (who escalated, what gap, what workaround they tried)
    # before the recommendation rationale. Presence-driven emission
    # (the existing exporter rule): section is rendered only when
    # `parsed_data["escalation"]` exists, so Alfred-form requests
    # produce byte-identical output to pre-item-5 (no spurious empty
    # "## Escalation" header for non-worker filings).
    # Field naming preserves CLAUDE.md §6 schema verbatim — Worker,
    # Gap, Workaround used. Unified `# Tool Request:` H1 rendering
    # per items-5+6 Finding F reframe (Option β); the prototype-era
    # "# Worker Escalation:" H1 form is subsumed into the unified
    # Tool Request shape with this dedicated section.
    (
        "Escalation",
        [
            ("Worker", "worker"),
            ("Gap", "gap"),
            ("Workaround used", "workaround_used"),
        ],
    ),
    (
        "Recommendation",
        [
            ("Why this tool", "why_this_tool"),
            ("Alternatives considered", "alternatives_considered"),
            ("Risk/cost", "risk_cost"),
            ("Confidence", "confidence"),
            ("Source", "source"),
            ("Evidence", "evidence"),
        ],
    ),
    (
        "Approval",
        [
            ("Decision", "decision"),
            ("Conditions", "conditions"),
            ("Date", "date"),
        ],
    ),
    (
        "Install",
        [
            ("Command run", "command_run"),
            ("Verification", "verification"),
            ("Date", "date"),
        ],
    ),
    (
        "First Use",
        [
            ("Task", "task"),
            ("Result", "result"),
            ("Date", "date"),
        ],
    ),
    (
        "Outcome",
        [
            ("Verdict", "verdict"),
            ("Notes", "notes"),
            ("Date", "date"),
        ],
    ),
]

def export_to_markdown(req: Request) -> str:
    """Render a Request back to the canonical tool-request markdown format.

    Inverse of `parse_request_file`. Round-trip preserves semantic content:
    parse(export(parse(x))) == parse(x). Emission is presence-driven — a
    section is emitted only if present in `parsed_data`, and a field is
    emitted only if its key exists in the section dict (even when the
    value is empty string).
    """
    parsed = req.parsed_data or {}
    lines: list[str] = [
        f"status: {req.status}",
        "",
        f"# Tool Request: {req.tool_name}",
        "",
    ]

    for section_name, fields in _EXPORT_SECTIONS:
        section_key = section_name.lower().replace(" ", "_")
        section_data = parsed.get(section_key)
        if section_data is None:
            continue
        lines.append(f"## {section_name}")
        lines.append("")
        for label, key in fields:
            if key not in section_data:
                continue
            raw_value = section_data[key]
            if key == "discovered":
                value_str = "true" if raw_value else "false"
            else:
                value_str = str(raw_value)
            lines.append(f"- **{label}:** {value_str}".rstrip())
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _upsert_request(
    session: Session, parsed: ParsedRequest, stats: IngestStats
) -> None:
    existing = (
        session.query(Request).filter_by(filename=parsed.filename).one_or_none()
    )
    fields = dict(
        folder=parsed.folder,
        status=parsed.status,
        tool_name=parsed.tool_name,
        tool_slug=parsed.tool_slug,
        category=parsed.category,
        confidence=parsed.confidence,
        is_discovered=parsed.is_discovered,
        raw_markdown=parsed.raw_markdown,
        parsed_data=parsed.sections,
    )
    if existing is None:
        session.add(Request(filename=parsed.filename, **fields))
        stats.ingested += 1
    else:
        for k, v in fields.items():
            setattr(existing, k, v)
        stats.updated += 1
