"""Pydantic/dataclass shapes used across the lifecycle-store package
and the /requests API.

These are distinct from:

- `core.db.models.Request` — the SQLAlchemy row; persistence layer
- `core.ingest.tool_requests.ParsedRequest` — the file-parse result;
  dense (carries raw_markdown, full section tree)

The shapes here are the **service-layer surface**: what callers of
`LifecycleService.create_request(...)` / `.list_pending(...)` /
`.update_status(...)` send in and receive back. Operational-first
log lines and API response bodies both project from these.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


FolderName = Literal["pending", "resolved", "archived"]


@dataclass(frozen=True)
class LifecycleStats:
    """Summary of a `reconcile()` pass over the three-folder layout.

    Emitted once at startup via the FastAPI lifespan hook; its
    counts become the operator's first sign the lifecycle store is
    healthy (or flag the count of unparseable files).
    """

    scanned: int = 0
    inserted: int = 0
    updated: int = 0
    unparseable: int = 0


class NewRequestDraft(BaseModel):
    """Minimal fields required to file a new pending tool request.

    The server derives filename, timestamp, and raw_markdown from
    these fields plus the X10 template. Callers do not supply raw
    markdown — the writer owns format fidelity so a caller can't
    produce a file the cron (X11) can't parse.

    Stage 1A item 5 additions (worker-to-Alfred escalation routing):

    - ``agent_id`` — codename of the filing agent (e.g. ``"scout"``).
      Lives in `parsed_data["escalation"]["worker"]` post-write, not
      in a dedicated DB column (Path A per items-5+6 Decision 1 —
      schema parsimony). Worker codenames drive the filename prefix
      (`worker-<agent>-<slug>`).
    - ``escalation_target`` — routing target for the approval. Stored
      as a real column for the Alfred-facing review queue query;
      validated at the CLI surface and at the API query parameter via
      `core.lifecycle_store.escalation.ESCALATION_TARGET_VALUES`.
    - ``gap`` / ``workaround_used`` — worker-form-specific bullets.
      Live in `parsed_data["escalation"]` via the writer; no dedicated
      columns. Required when the draft is worker-form (CLI enforces
      per Decision N2a).
    """

    tool_name: str = Field(..., min_length=1)
    category: Optional[str] = None
    install_method: Optional[str] = None
    task_context: Optional[str] = None
    why_this_tool: Optional[str] = None
    alternatives_considered: Optional[str] = None
    risk_cost: Optional[str] = None
    confidence: Optional[Literal["high", "medium", "low"]] = None
    is_discovered: bool = False
    source: Optional[str] = None
    evidence: Optional[str] = None
    # Stage 1A item 5 — escalation-routing fields. All Optional /
    # default None so existing Alfred-form callers (incl. the MCP
    # meta-tool, which stays unchanged per items-5+6 Decision 3) keep
    # working byte-for-byte. The CLI surface enforces worker-form
    # required-field semantics (--gap + --workaround) per Decision N2a;
    # the server accepts whatever the CLI lets through.
    agent_id: Optional[str] = None
    escalation_target: Optional[Literal["alfred", "operator"]] = None
    gap: Optional[str] = None
    workaround_used: Optional[str] = None


class StatusChange(BaseModel):
    """Payload for `POST /requests/{id}/status`.

    Status must be a legal file-side value per
    `core.lifecycle_policy` vocabulary. Transition legality is
    validated in the service layer; invalid transitions raise
    `InvalidTransitionError` and surface as HTTP 409.
    """

    status: str = Field(..., min_length=1)
    decision: Optional[str] = None
    conditions: Optional[str] = None
    notes: Optional[str] = None
    session_id: Optional[str] = Field(
        None,
        description=(
            "Optional session identifier for telemetry correlation "
            "(Fix Day 4 Task 6 — session_id propagation). When an "
            "approve transition triggers a successful install, this "
            "value populates the `installed` ToolUsageEvent's "
            "session_id column. UI-originated approvals from the "
            "browser leave this null; future MCP-originated approvals "
            "may pass the shim's SHIM_SESSION_ID."
        ),
    )


class ListedRequest(BaseModel):
    """One entry in `GET /requests/pending` / related list responses.

    Operational-first: parse failures surface here with
    `is_parseable=False` + `parse_error` rather than being excluded
    or raising at the list endpoint. A log reader sees the bad file;
    a UI reader sees it flagged; the endpoint stays up.
    """

    id: Optional[int] = None
    filename: str
    folder: FolderName
    status: Optional[str] = None
    tool_name: Optional[str] = None
    tool_slug: Optional[str] = None
    category: Optional[str] = None
    confidence: Optional[str] = None
    is_discovered: Optional[bool] = None
    # Stage 1A item 5 — surfaced from the indexed `Request.escalation_target`
    # column. The "who reviews this" hint for the listing reader (Alfred-
    # facing CLI, future inbox UI). NULL on Alfred-form filings (zero
    # behavior change for pre-item-5 rows). agent_id is intentionally
    # NOT surfaced here (lives in parsed_data per Path A); operators
    # who need the per-agent identity click through to RequestDetail.
    escalation_target: Optional[str] = None
    is_parseable: bool = True
    parse_error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    age_days: Optional[int] = None  # rendered at list time; supports `stale` filter


class RequestDetail(ListedRequest):
    """Full detail response for `GET /requests/{id}`. Adds the raw
    markdown so the UI can render without re-reading the file.
    """

    raw_markdown: Optional[str] = None
