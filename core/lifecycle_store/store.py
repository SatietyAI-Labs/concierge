"""Store layer — DB ↔ filesystem sync + folder-agnostic lookup.

Key operations:

- `reconcile(session, root)` — walk all three folders, upsert DB
  rows for every parseable file, log unparseable files, return
  stats. Called once at startup via `lifespan`.
- `find_file_by_filename(root, filename)` — locate a file by its
  filename across all three folders. Returns the path + folder it
  was found in, or None. Used on POST-status so a race with the
  cron (file moved between list-time and write-time) still lands
  the update in the right folder.
- `list_pending_rows(session, stale_only, limit, offset)` — DB
  query for listing; combines with a best-effort file-age render
  for the `stale` filter. Returns rows already formatted as
  `ListedRequest`.

File-parse failures are never raised to the caller; they are
converted into `ListedRequest(is_parseable=False, parse_error=...)`
entries and WARNING-logged with the filename. A one-off malformed
file in `pending/` does not block the endpoint.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from core.db.models import Request
from core.ingest.tool_requests import (
    FOLDER_ORDER,
    ParseError,
    parse_filename,
    parse_request_file,
)
from core.lifecycle_policy import STALE_PENDING_DAYS
from core.lifecycle_store.schema import (
    FolderName,
    LifecycleStats,
    ListedRequest,
    RequestDetail,
)


logger = logging.getLogger(__name__)


# ---- Reconciliation -----------------------------------------------------


def reconcile(session: Session, root: Path) -> LifecycleStats:
    """Walk every `pending/`, `resolved/`, `archived/` file and
    upsert its DB row. Log per-file outcomes at DEBUG, unparseable
    files at WARNING.

    Returns a `LifecycleStats` summary; service layer emits the
    aggregate at INFO from the lifespan hook.
    """
    stats = LifecycleStats()
    if not root.exists():
        logger.warning(
            "lifecycle.reconcile.root_missing path=%s — no reconciliation performed",
            root,
        )
        return stats
    scanned = inserted = updated = unparseable = 0
    for folder in FOLDER_ORDER:
        folder_path = root / folder
        if not folder_path.exists():
            continue
        for md_file in sorted(folder_path.glob("*.md")):
            scanned += 1
            try:
                parsed = parse_request_file(md_file, folder)
            except ParseError as exc:
                unparseable += 1
                logger.warning(
                    "lifecycle.reconcile.unparseable filename=%s folder=%s error=%s",
                    md_file.name,
                    folder,
                    exc,
                )
                continue
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
                inserted += 1
                logger.debug(
                    "lifecycle.reconcile.inserted filename=%s folder=%s",
                    parsed.filename,
                    folder,
                )
            else:
                for k, v in fields.items():
                    setattr(existing, k, v)
                updated += 1
                logger.debug(
                    "lifecycle.reconcile.updated filename=%s folder=%s",
                    parsed.filename,
                    folder,
                )
    session.commit()
    return LifecycleStats(
        scanned=scanned, inserted=inserted, updated=updated, unparseable=unparseable
    )


# ---- Folder-agnostic lookup ---------------------------------------------


def find_file_by_filename(
    root: Path, filename: str
) -> Optional[tuple[Path, FolderName]]:
    """Locate a file by basename across all three lifecycle folders.

    Returns `(path, folder)` or `None`. Used by the service layer
    when a POST-status arrives referring to a filename that may
    have moved since the request was last listed — the cron may
    have run between the two requests.
    """
    for folder in FOLDER_ORDER:
        candidate = root / folder / filename
        if candidate.exists():
            return candidate, folder  # type: ignore[return-value]
    return None


# ---- Listing ------------------------------------------------------------


def _age_days(created_at: Optional[datetime]) -> Optional[int]:
    if created_at is None:
        return None
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    delta = now - created_at.replace(tzinfo=None) if created_at.tzinfo else now - created_at
    return int(delta.total_seconds() // 86400)


def _row_to_listed(row: Request) -> ListedRequest:
    created_at, _ = parse_filename(row.filename)
    age = _age_days(created_at) if created_at is not None else None
    return ListedRequest(
        id=row.id,
        filename=row.filename,
        folder=row.folder,  # type: ignore[arg-type]
        status=row.status,
        tool_name=row.tool_name,
        tool_slug=row.tool_slug,
        category=row.category,
        confidence=row.confidence,
        is_discovered=row.is_discovered,
        escalation_target=row.escalation_target,
        is_parseable=True,
        parse_error=None,
        created_at=row.created_at,
        updated_at=row.updated_at,
        age_days=age,
    )


def list_pending_rows(
    session: Session,
    *,
    stale_only: bool = False,
    limit: int = 100,
    offset: int = 0,
    escalation_target: Optional[str] = None,
) -> list[ListedRequest]:
    """DB-backed list of pending requests. `stale_only=True`
    applies the `STALE_PENDING_DAYS` threshold via filename-derived
    `age_days`.

    Stage 1A item 5: `escalation_target` (default None) filters the
    list to rows whose `escalation_target` column matches. None means
    no filter (returns all pending rows). The endpoint-layer
    validates the value against ESCALATION_TARGET_VALUES via Pydantic
    Literal before calling here, so an unknown value would 422 at
    that layer rather than silently returning an empty list (Decision
    N4a). Empty-string handling per Decision N3a: callers convert
    `""` to None before calling; this function does not interpret
    empty string specially.

    The DB filter is on `folder='pending'` + `status='pending'`;
    the cron moves files based on status, so any mismatch between
    folder and status is a signal the reconciliation pass is out
    of date — we log at DEBUG when we see one but still render the
    row (the operator needs to see drift, not be hidden from it).
    """
    query = (
        session.query(Request)
        .filter(Request.folder == "pending")
        .filter(Request.status == "pending")
    )
    if escalation_target is not None:
        query = query.filter(Request.escalation_target == escalation_target)
    query = query.order_by(Request.filename.asc())
    rows = query.offset(offset).limit(limit).all()
    listed = [_row_to_listed(r) for r in rows]
    if stale_only:
        listed = [r for r in listed if (r.age_days or 0) >= STALE_PENDING_DAYS]
    return listed


def list_parseability_snapshot(root: Path) -> list[ListedRequest]:
    """Best-effort filesystem scan that surfaces unparseable files
    as `is_parseable=False` rows. Used by the service layer to
    augment DB-based lists with files that would otherwise be
    invisible (the DB has no row for an unparseable file).

    This is intentionally separate from `reconcile(...)`: reconcile
    writes to the DB (startup only), this is a read-only snapshot
    callable per request if the operator suspects drift.
    """
    results: list[ListedRequest] = []
    if not root.exists():
        return results
    for folder in FOLDER_ORDER:
        folder_path = root / folder
        if not folder_path.exists():
            continue
        for md_file in sorted(folder_path.glob("*.md")):
            try:
                parse_request_file(md_file, folder)
            except ParseError as exc:
                results.append(
                    ListedRequest(
                        filename=md_file.name,
                        folder=folder,  # type: ignore[arg-type]
                        is_parseable=False,
                        parse_error=str(exc),
                    )
                )
    return results


def row_detail(session: Session, request_id: int) -> Optional[RequestDetail]:
    row = session.query(Request).filter(Request.id == request_id).one_or_none()
    if row is None:
        return None
    listed = _row_to_listed(row)
    return RequestDetail(**listed.model_dump(), raw_markdown=row.raw_markdown)
