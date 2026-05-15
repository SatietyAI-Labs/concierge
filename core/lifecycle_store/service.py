"""Service orchestrator for the lifecycle store.

Wraps parser + writer + store + transition validation into the
four operations the `/requests` API surfaces:

- `create_request(draft)` — write a new pending file + insert DB row
- `update_status(filename, change)` — validate transition, update
  file status line, update DB row, log INFO line
- `list_pending(stale, limit, offset)` — DB-backed list with
  file-system parseability overlay so unparseable files are visible
- `get_request(request_id)` — DB row + raw_markdown for detail

**Scope boundary — N7 is lifecycle visibility + state transitions,
not lifecycle action.** Approving a request writes the file and the
DB row; it does NOT execute `pip install …` or any other tool
install. The approve-triggers-install wiring belongs to X13 (Day 3,
Cut 2 deferrable). An operator reading 48h shakedown logs must see
the distinction between a state-change event (this module's
concern) and an install-execution event (X13's concern). Per
DECISIONS `[2026-04-22 08:34]`, the policy-vs-store module split
exists precisely to keep the two readable apart.

Logging discipline mirrors N6's service:

- One INFO line per state change with request_id, filename,
  old_status → new_status, folder
- DEBUG for per-operation context (file path, byte counts)
- WARNING on file-parse failures (emitted by the store during
  reconcile and list)
- Counters bump for created / transitioned / parse-failed /
  invalid-transition; shutdown summary via a later hook if needed
"""
from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from sqlalchemy.orm import Session

from core.db.models import Request
from core.ingest.tool_requests import (
    ParseError,
    parse_filename,
    parse_request_file,
    slugify,
)
from core.lifecycle_store.schema import (
    FolderName,
    ListedRequest,
    NewRequestDraft,
    RequestDetail,
    StatusChange,
)
from core.lifecycle_store.store import (
    find_file_by_filename,
    list_parseability_snapshot,
    list_pending_rows,
    row_detail,
)
from core.lifecycle_store.transitions import (
    InvalidTransitionError,
    VALID_FILE_STATUSES,
    assert_valid_transition,
)
from core.lifecycle_store.escalation import worker_filename_prefix
from core.lifecycle_store.writer import (
    generate_filename,
    update_install_section,
    update_status_line,
    write_new_request,
)
from core.db.models import Tool
from core.install.provenance import PROVENANCE_BY_RESULT_METHOD
from core.install.schemas import InstallResult
from core.install.service import install_by_method, normalize_install_method
from core.events import EventBroker
from core.telemetry import emit_usage_event


# Signature for the install dispatcher so tests can inject a stub
# without triggering real pip/npm subprocess calls. Matches the
# `install_by_method` positional + keyword contract.
InstallDispatcher = Callable[..., Optional[InstallResult]]


logger = logging.getLogger(__name__)


@dataclass
class LifecycleCounters:
    """In-process counters — same shape as recommend.counters, scoped
    to the lifecycle store's operational events.
    """

    created: int = 0
    transitioned: int = 0
    invalid_transitions: int = 0
    parse_failed: int = 0
    not_found: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_create(self) -> None:
        with self._lock:
            self.created += 1

    def record_transition(self) -> None:
        with self._lock:
            self.transitioned += 1

    def record_invalid_transition(self) -> None:
        with self._lock:
            self.invalid_transitions += 1

    def record_parse_failed(self) -> None:
        with self._lock:
            self.parse_failed += 1

    def record_not_found(self) -> None:
        with self._lock:
            self.not_found += 1

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "created": self.created,
                "transitioned": self.transitioned,
                "invalid_transitions": self.invalid_transitions,
                "parse_failed": self.parse_failed,
                "not_found": self.not_found,
            }


_counters: Optional[LifecycleCounters] = None
_counters_lock = threading.Lock()


def get_counters() -> LifecycleCounters:
    global _counters
    if _counters is None:
        with _counters_lock:
            if _counters is None:
                _counters = LifecycleCounters()
    return _counters


def reset_counters_for_tests() -> None:
    global _counters
    with _counters_lock:
        _counters = LifecycleCounters()


# ---- Exceptions surfaced to callers -------------------------------------


class RequestNotFoundError(LookupError):
    """Raised when a caller references a request (by id or filename)
    that the store cannot locate. Endpoint-layer translates to 404.
    """


# ---- Service ------------------------------------------------------------


@dataclass
class LifecycleService:
    session: Session
    lifecycle_root: Path
    counters: LifecycleCounters = None  # type: ignore[assignment]
    install_dispatcher: InstallDispatcher = field(default=install_by_method)
    # Fix Day 4 Task 4 — optional SSE broker for `new_request` fan-out.
    # Per Fork D, service-layer publishes (not endpoint-layer) so any
    # non-HTTP filing path eventually added (e.g. future MCP-originated
    # create_request) also feeds the same broker without a second
    # wiring step. None = no broker wired (unit tests that don't care
    # about SSE construct without one).
    event_broker: Optional["EventBroker"] = None

    def __post_init__(self) -> None:
        if self.counters is None:
            self.counters = get_counters()

    def _short_id(self) -> str:
        return uuid.uuid4().hex[:12]

    # ---- Create ---------------------------------------------------------

    def create_request(self, draft: NewRequestDraft) -> RequestDetail:
        request_id = self._short_id()
        # Stage 1A item 5 — worker filings get the `worker-<name>-` prefix
        # in the filename per CLAUDE.md §6 so operators can grep
        # `pending/worker-*` for the escalation queue. Alfred-form
        # filings keep the bare `YYYY-MM-DD-HHMM-<slug>.md` shape
        # (agent_prefix=None preserves pre-item-5 behavior).
        filename = generate_filename(
            tool_name=draft.tool_name,
            agent_prefix=worker_filename_prefix(draft.agent_id),
        )
        # Ensure filename uniqueness; the YYYY-MM-DD-HHMM resolution
        # collides only if two requests for the same tool-slug land in
        # the same minute — add a uniqueness suffix in that narrow case.
        filename = self._ensure_unique_filename(filename)

        try:
            path = write_new_request(
                lifecycle_root=self.lifecycle_root,
                draft=draft,
                filename=filename,
            )
        except Exception as exc:
            logger.error(
                "lifecycle.create_request.write_failed request_id=%s filename=%s error=%s: %s",
                request_id,
                filename,
                type(exc).__name__,
                exc,
            )
            raise

        # Parse-back-then-upsert so the DB reflects exactly what the
        # cron will see. Any shape discrepancy between the writer
        # and parser surfaces here, not mid-soak.
        try:
            parsed = parse_request_file(path, "pending")
        except ParseError as exc:
            self.counters.record_parse_failed()
            logger.error(
                "lifecycle.create_request.roundtrip_parse_failed request_id=%s "
                "filename=%s error=%s",
                request_id,
                filename,
                exc,
            )
            raise

        row = Request(
            filename=parsed.filename,
            folder="pending",
            status=parsed.status,
            tool_name=parsed.tool_name,
            tool_slug=parsed.tool_slug,
            category=parsed.category,
            confidence=parsed.confidence,
            is_discovered=parsed.is_discovered,
            # Stage 1A item 5 — escalation routing target persists on the
            # column (indexed for the Alfred-facing review queue query).
            # NULL for Alfred-form filings; one of `"alfred"` /
            # `"operator"` per ESCALATION_TARGET_VALUES otherwise. The
            # draft.escalation_target value flows straight through;
            # Pydantic Literal validation already ran on the draft.
            escalation_target=draft.escalation_target,
            raw_markdown=parsed.raw_markdown,
            parsed_data=parsed.sections,
        )
        self.session.add(row)
        self.session.commit()

        self.counters.record_create()
        logger.info(
            "lifecycle.create request_id=%s filename=%s tool_slug=%s "
            "is_discovered=%s folder=pending escalation_target=%s",
            request_id,
            filename,
            parsed.tool_slug,
            parsed.is_discovered,
            draft.escalation_target,
        )

        # Fix Day 4 Task 4 — SSE `new_request` fan-out. Broker is
        # optional: tests / non-API callers construct without one and
        # the publish becomes a no-op. Publish AFTER the DB commit so
        # subscribers never see an event for a row that rolled back.
        if self.event_broker is not None:
            self.event_broker.publish(
                {
                    "event": "new_request",
                    "data": {
                        "filename": parsed.filename,
                        "tool_name": parsed.tool_name,
                        "tool_slug": parsed.tool_slug,
                        "category": parsed.category,
                        "confidence": parsed.confidence,
                        "is_discovered": parsed.is_discovered,
                    },
                }
            )

        return RequestDetail(
            id=row.id,
            filename=row.filename,
            folder="pending",
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
            raw_markdown=row.raw_markdown,
        )

    def _ensure_unique_filename(self, filename: str) -> str:
        """If `filename` already exists anywhere in the lifecycle
        tree, return a disambiguated variant; otherwise return as-is.
        """
        if find_file_by_filename(self.lifecycle_root, filename) is None:
            return filename
        stem, suffix = filename[:-3], filename[-3:]
        # -2, -3, ... until we find one that doesn't exist.
        for n in range(2, 100):
            candidate = f"{stem}-{n}{suffix}"
            if find_file_by_filename(self.lifecycle_root, candidate) is None:
                return candidate
        raise FileExistsError(
            f"could not produce a unique filename for base {filename!r} "
            "(100 variants all exist)"
        )

    # ---- Update status --------------------------------------------------

    def update_status(
        self, *, filename: str, change: StatusChange
    ) -> RequestDetail:
        request_id = self._short_id()

        if change.status not in VALID_FILE_STATUSES:
            self.counters.record_invalid_transition()
            raise InvalidTransitionError(
                f"status {change.status!r} is not a recognized file-side status "
                f"(valid: {sorted(VALID_FILE_STATUSES)})"
            )

        # Folder-agnostic lookup: the cron may have moved the file
        # between list time and this request. Log which folder we
        # actually found it in.
        located = find_file_by_filename(self.lifecycle_root, filename)
        if located is None:
            self.counters.record_not_found()
            raise RequestNotFoundError(f"no file named {filename!r} in lifecycle root")
        path, folder = located

        # Parse current state to validate the transition.
        try:
            parsed = parse_request_file(path, folder)
        except ParseError as exc:
            self.counters.record_parse_failed()
            logger.error(
                "lifecycle.update_status.parse_failed request_id=%s filename=%s "
                "folder=%s error=%s",
                request_id,
                filename,
                folder,
                exc,
            )
            raise

        try:
            assert_valid_transition(current=parsed.status, target=change.status)
        except InvalidTransitionError:
            self.counters.record_invalid_transition()
            logger.warning(
                "lifecycle.invalid_transition request_id=%s filename=%s "
                "current=%s target=%s",
                request_id,
                filename,
                parsed.status,
                change.status,
            )
            raise

        # Write the new status line to file (atomic) before updating
        # the DB — file is source of truth; if file write fails we
        # do not corrupt the DB row.
        update_status_line(path=path, new_status=change.status)

        row = (
            self.session.query(Request)
            .filter(Request.filename == filename)
            .one_or_none()
        )
        if row is None:
            # Reconcile-on-demand: file exists but DB row doesn't.
            # Parse and insert.
            new_parsed = parse_request_file(path, folder)
            row = Request(
                filename=new_parsed.filename,
                folder=folder,
                status=new_parsed.status,
                tool_name=new_parsed.tool_name,
                tool_slug=new_parsed.tool_slug,
                category=new_parsed.category,
                confidence=new_parsed.confidence,
                is_discovered=new_parsed.is_discovered,
                raw_markdown=new_parsed.raw_markdown,
                parsed_data=new_parsed.sections,
            )
            self.session.add(row)
        else:
            # Re-parse to pick up any change to the raw_markdown
            # (the status line change alone is enough but future
            # status changes may include section edits).
            refreshed = parse_request_file(path, folder)
            row.status = refreshed.status
            row.folder = folder
            row.raw_markdown = refreshed.raw_markdown
            row.parsed_data = refreshed.sections
        self.session.commit()

        self.counters.record_transition()
        logger.info(
            "lifecycle.transition request_id=%s filename=%s "
            "old_status=%s new_status=%s folder=%s",
            request_id,
            filename,
            parsed.status,
            change.status,
            folder,
        )

        detail = RequestDetail(
            id=row.id,
            filename=row.filename,
            folder=folder,
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
            raw_markdown=row.raw_markdown,
        )

        # X13 wire-in: approving a request with a canonical install
        # method auto-installs and transitions to installed/failed.
        # Non-canonical methods (mcp-server pre-T5, unknown, empty)
        # leave status=approved for operator handling. Fix Day 4 Task
        # 6: session_id flows from StatusChange into the install emit
        # site — UI-originated approvals pass null (no MCP session to
        # correlate against); MCP-originated approvals (future) carry
        # the shim's SHIM_SESSION_ID.
        if change.status == "approved":
            follow_up = self._maybe_install_on_approve(
                filename=filename,
                path=path,
                parsed=parsed,
                session_id=change.session_id,
            )
            if follow_up is not None:
                detail = follow_up

        return detail

    # ---- X13 wire-in ----------------------------------------------------

    def _maybe_install_on_approve(
        self,
        *,
        filename: str,
        path: Path,
        parsed,
        session_id: Optional[str] = None,
    ) -> Optional[RequestDetail]:
        """Post-approval install dispatch. Returns the RequestDetail
        from the follow-up installed/failed transition, or None when
        no install was attempted (manual-handling path).

        `session_id` (Fix Day 4 Task 6) flows into the `installed`
        ToolUsageEvent emit on success. Null when caller didn't
        provide one (e.g. UI-originated approvals).
        """
        request_section = parsed.sections.get("request", {})
        install_method_raw = (request_section.get("install_method") or "").strip()
        tool_name = (
            request_section.get("tool_suggested") or parsed.tool_name
        ).strip()

        canonical = normalize_install_method(install_method_raw)
        if canonical is None:
            logger.info(
                "lifecycle.install_manual filename=%s install_method=%r "
                "— leaving status=approved for operator",
                filename,
                install_method_raw,
            )
            return None

        try:
            result = self.install_dispatcher(
                install_method_raw, tool_name=tool_name
            )
        except Exception as exc:
            logger.error(
                "lifecycle.install_dispatch_failed filename=%s error=%s: %s",
                filename,
                type(exc).__name__,
                exc,
            )
            return None

        if result is None:
            logger.info(
                "lifecycle.install_skipped filename=%s "
                "— dispatcher returned None (missing params, operator handles)",
                filename,
            )
            return None

        verification = (
            f"exit={result.returncode} ok"
            if result.success
            else f"exit={result.returncode} stderr_head={(result.stderr or '')[:120]!r}"
        )
        try:
            update_install_section(
                path=path,
                command_run=result.command,
                verification=verification,
            )
        except Exception as exc:
            logger.error(
                "lifecycle.install_section_write_failed filename=%s error=%s: %s",
                filename,
                type(exc).__name__,
                exc,
            )
            return None

        follow_up_status = "installed" if result.success else "failed"
        logger.info(
            "lifecycle.install_done filename=%s method=%s success=%s "
            "returncode=%d elapsed_ms=%d",
            filename,
            result.method,
            result.success,
            result.returncode,
            result.elapsed_ms,
        )

        # §D usage telemetry — emit on successful install only. Failed
        # installs leave the tool's lifecycle_state unchanged; no event
        # to record. Fix Day 4 Task 6: session_id flows from the
        # StatusChange payload through `update_status` into this emit;
        # null when the approval came from a non-MCP caller (e.g. UI).
        if result.success:
            tool_slug = slugify(tool_name)
            try:
                emit_usage_event(
                    self.session,
                    tool_slug=tool_slug,
                    event_type="installed",
                    context={
                        "filename": filename,
                        "install_method": result.method,
                        "elapsed_ms": result.elapsed_ms,
                    },
                    session_id=session_id,
                )
            except Exception as exc:
                logger.warning(
                    "lifecycle.telemetry_emit_failed filename=%s "
                    "tool_slug=%s error=%s: %s",
                    filename, tool_slug, type(exc).__name__, exc,
                )

            # Decision C+D wire-in: set Tool.install_method_provenance
            # per the runtime translation map. Non-fatal — a missing
            # Tool row or DB error logs and proceeds; provenance is
            # informational, not a transactional requirement.
            provenance = PROVENANCE_BY_RESULT_METHOD.get(result.method)
            if provenance is not None:
                try:
                    tool_row = (
                        self.session.query(Tool)
                        .filter(Tool.slug == tool_slug)
                        .first()
                    )
                    if tool_row is not None:
                        tool_row.install_method_provenance = provenance
                except Exception as exc:
                    logger.warning(
                        "lifecycle.provenance_update_failed filename=%s "
                        "tool_slug=%s error=%s: %s",
                        filename, tool_slug, type(exc).__name__, exc,
                    )

        return self.update_status(
            filename=filename,
            change=StatusChange(status=follow_up_status),
        )

    # ---- Read -----------------------------------------------------------

    def list_pending(
        self,
        *,
        stale: bool = False,
        limit: int = 100,
        offset: int = 0,
        escalation_target: Optional[str] = None,
    ) -> list[ListedRequest]:
        rows = list_pending_rows(
            self.session,
            stale_only=stale,
            limit=limit,
            offset=offset,
            escalation_target=escalation_target,
        )
        # Augment with any unparseable files currently in pending/.
        # They're invisible to the DB-based list; surface them here
        # so the UI (and a log reader) can see them. Unparseable
        # files have no escalation_target context (they couldn't be
        # parsed) — when an escalation_target filter is applied, we
        # omit the unparseable overlay so the result represents only
        # rows the filter applies to. Without a filter, unparseable
        # files surface as before (operational-first per N7 scope).
        if escalation_target is None:
            snapshot = [
                r
                for r in list_parseability_snapshot(self.lifecycle_root)
                if r.folder == "pending" and not r.is_parseable
            ]
            return rows + snapshot
        return rows

    def get_request(self, request_id: int) -> Optional[RequestDetail]:
        return row_detail(self.session, request_id)
