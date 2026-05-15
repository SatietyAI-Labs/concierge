"""Atomic file operations for the three-folder lifecycle store.

Two write primitives:

1. `write_new_request(...)` — build full markdown from a
   `NewRequestDraft`, write atomically to `pending/<filename>`.
2. `update_status_line(...)` — read an existing file, replace the
   first-line status, write atomically back to the **same folder
   the file is currently in** (which may not be where it started,
   if the cron moved it between read and write).

Both use tempfile + `os.replace` so cron-side readers never see a
truncated or partially-written file. File encoding is UTF-8 with
`\\n` line endings; the source corpus was written this way and the
cron's awk parsing assumes it.
"""
from __future__ import annotations

import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.ingest.tool_requests import (
    export_to_markdown,
    parse_request_file,
    slugify,
)
from core.lifecycle_store.schema import NewRequestDraft


logger = logging.getLogger(__name__)


_STATUS_LINE_RE = re.compile(r"^status:\s*\S.*$", re.MULTILINE)


def generate_filename(
    *,
    tool_name: str,
    when: Optional[datetime] = None,
    agent_prefix: Optional[str] = None,
) -> str:
    """Build a filename from a tool name. `when=None` defaults to
    `datetime.now()`.

    Two shapes:

    - Default: ``YYYY-MM-DD-HHMM-<slug>.md`` (Alfred form, pre-item-5
      back-compat).
    - With `agent_prefix`: ``YYYY-MM-DD-HHMM-<prefix>-<slug>.md`` —
      Stage 1A item 5 worker-form convention per CLAUDE.md §6. The
      prefix renders as-is (caller controls case + content), but
      passes through `slugify` to normalize whitespace and punctuation
      to the same alnum-hyphen form as the slug. Typical caller
      value: ``"worker-scout"`` (built by
      `core.lifecycle_store.escalation.worker_filename_prefix`).

    Filename slug is derived from the tool name via the shared
    `slugify(...)` helper (N3 parser) so the filename sort order
    matches the DB-side tool_slug sort.
    """
    dt = when if when is not None else datetime.now()
    parts: list[str] = [f"{dt:%Y-%m-%d-%H%M}"]
    if agent_prefix:
        parts.append(slugify(agent_prefix))
    parts.append(slugify(tool_name))
    stem = "-".join(parts)
    return f"{stem}.md"


def build_markdown(draft: NewRequestDraft) -> str:
    """Render a `NewRequestDraft` into the canonical X10 markdown
    format. Delegates section composition to the shared
    `export_to_markdown(...)` — we construct a synthetic
    `Request`-shaped object so the shared exporter does the lifting.

    Stage 1A item 5 extension: when the draft carries worker-form
    fields (`agent_id` naming a worker, or `gap` / `workaround_used`
    populated), an additional `escalation` section is added to the
    parsed_data dict. The shared exporter emits the section
    presence-driven (only when the key exists), so Alfred-form drafts
    produce byte-identical output to pre-item-5 (back-compat invariant
    pinned in `tests/test_lifecycle_service_escalation.py`).
    """
    # Reuse N3's exporter by projecting the draft into the shape
    # `export_to_markdown` expects (an object with `.status`,
    # `.tool_name`, `.parsed_data`). Constructing a real Request
    # here would couple writer to SQLAlchemy; a lightweight
    # stand-in keeps the writer testable in isolation.

    class _Stand:
        pass

    stand = _Stand()
    stand.status = "pending"
    stand.tool_name = draft.tool_name
    request_section = {
        "task_context": draft.task_context or "",
        "tool_suggested": draft.tool_name,
        "category": draft.category or "",
        "install_method": draft.install_method or "",
        "discovered": draft.is_discovered,
    }
    recommendation_section = {
        "why_this_tool": draft.why_this_tool or "",
        "alternatives_considered": draft.alternatives_considered or "",
        "risk_cost": draft.risk_cost or "",
        "confidence": draft.confidence or "",
    }
    if draft.source is not None:
        recommendation_section["source"] = draft.source
    if draft.evidence is not None:
        recommendation_section["evidence"] = draft.evidence

    # Approval stub so the file shape matches what operators
    # (humans + Alfred) expect to fill in. All fields empty; the
    # parser tolerates empty values.
    approval_section: dict = {"decision": "", "conditions": "", "date": ""}

    parsed_data: dict[str, dict] = {
        "request": request_section,
        "recommendation": recommendation_section,
        "approval": approval_section,
    }

    # Stage 1A item 5 — Escalation section emitted only when the
    # draft carries worker-form content. Lazy-import the predicate to
    # avoid cycles (escalation.py imports nothing from this module
    # today, but the directionality matters if a future refactor
    # crosses the lines).
    from core.lifecycle_store.escalation import is_worker_form

    if is_worker_form(
        agent_id=draft.agent_id,
        escalation_target=draft.escalation_target,
        gap=draft.gap,
        workaround_used=draft.workaround_used,
    ):
        escalation_section: dict = {}
        if draft.agent_id:
            escalation_section["worker"] = draft.agent_id
        if draft.gap is not None:
            escalation_section["gap"] = draft.gap
        if draft.workaround_used is not None:
            escalation_section["workaround_used"] = draft.workaround_used
        parsed_data["escalation"] = escalation_section

    stand.parsed_data = parsed_data
    return export_to_markdown(stand)


def _atomic_write(path: Path, content: str) -> None:
    """Write `content` to `path` atomically.

    tempfile + `os.replace` keeps any reader — including the X11
    cron mid-scan — from ever observing a partial write. The temp
    file lives in the same directory as the target so `os.replace`
    is a same-filesystem rename.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path_str = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fp:
            fp.write(content)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(tmp_path, path)
    except Exception:
        # Clean up the tempfile on failure; best-effort.
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def write_new_request(
    *,
    lifecycle_root: Path,
    draft: NewRequestDraft,
    filename: str,
) -> Path:
    """Write a new `pending/` file from a draft. Returns the path.

    Fails loudly if the file already exists — overwriting an
    existing request would corrupt the cron's state machine. The
    caller (service layer) generates the filename and is responsible
    for ensuring uniqueness.
    """
    target = lifecycle_root / "pending" / filename
    if target.exists():
        raise FileExistsError(
            f"request file already exists: {target.name} — refusing to overwrite"
        )
    content = build_markdown(draft)
    _atomic_write(target, content)
    logger.info(
        "lifecycle.write_new filename=%s bytes=%d folder=pending",
        filename,
        len(content),
    )
    return target


def update_status_line(*, path: Path, new_status: str) -> None:
    """Replace the first-line `status:` in an existing file with
    `new_status`, atomically. Body of the file is otherwise
    preserved byte-for-byte.

    Raises `ValueError` if the file does not contain a parseable
    status line (defensive — the parser validates shape at read
    time, but a caller who passes a raw file this function hasn't
    seen gets a clear failure mode rather than a silent no-op).
    """
    content = path.read_text(encoding="utf-8")
    new_line = f"status: {new_status}"
    updated, n = _STATUS_LINE_RE.subn(new_line, content, count=1)
    if n == 0:
        raise ValueError(
            f"file {path.name} has no status line to update (path={path})"
        )
    _atomic_write(path, updated)
    logger.info(
        "lifecycle.update_status filename=%s new_status=%s folder=%s",
        path.name,
        new_status,
        path.parent.name,
    )


def update_install_section(
    *,
    path: Path,
    command_run: str,
    verification: str,
    date: Optional[str] = None,
) -> None:
    """Add or replace the Install section in a request file, atomically.

    Parse-modify-re-render path: reads the file, parses it, swaps the
    install section's three canonical fields, and re-emits via
    `export_to_markdown`. The file must be parseable before this is
    called; service-layer callers parse first to validate the
    transition, so the invariant holds by construction.

    Non-canonical prose in the file (comments, ad-hoc sections
    outside the canonical six) is NOT preserved — the canonical form
    is the spec. Operators who want to add ad-hoc notes should do so
    in the Approval section's 'Conditions' field, which round-trips.
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    parsed = parse_request_file(path, folder=path.parent.name)
    sections = dict(parsed.sections)
    sections["install"] = {
        "command_run": command_run,
        "verification": verification,
        "date": date,
    }

    class _Stand:
        pass

    stand = _Stand()
    stand.status = parsed.status
    stand.tool_name = parsed.tool_name
    stand.parsed_data = sections
    _atomic_write(path, export_to_markdown(stand))
    logger.info(
        "lifecycle.write_install filename=%s folder=%s",
        path.name,
        path.parent.name,
    )
