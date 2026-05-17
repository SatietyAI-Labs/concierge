"""SQLAlchemy 2.x declarative models for packs, tools, requests, and memory events."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from core.db.base import Base


TOOL_TYPE_VALUES = ("mcp", "cli", "http", "skill")
"""Peer categories per blueprint-v2 §Five Core Capabilities item #1.

Shared by Tool.tool_type and by ingest parsers so the constrained set
is declared once. Adding a new category requires a schema migration
that updates the Enum's CHECK constraint.
"""


LIFECYCLE_STATE_VALUES = (
    "discovered",
    "pending",
    "used",
    "loaded-on-boot",
    "retired",
    "pending-decision",
    "on-demand",
)
"""Tool-level lifecycle states per TOOL-CONCIERGE-OVERVIEW §Tool Lifecycle
Management and the blueprint-v2 §D audit (third state machine; distinct
from Request folder state and Request status field).

`pending-decision` is for tools the operator is actively evaluating
(distinct from `discovered`, which means known-but-not-loaded with no
active evaluation). Originates from the TOOL-MANIFEST.md "BUILDABLE"
section ("NOT YET BUILT" / "PARTIALLY BUILT" statuses) at ingest, or
from explicit operator action elsewhere. Transitions out: approve into
`loaded-on-boot` / `used`, deny into `retired`, park back to `discovered`.

`on-demand` is for a tool deliberately kept but NOT boot-loaded —
installed and usable, reachable on demand, deliberately off the boot
context budget (cf. master plan §IX context-weight philosophy). A
*settled* state, distinct from `pending-decision` ("fate undecided"):
`on-demand` says "we have decided to keep this, just not at boot."
The autonomous promotion scanner does not auto-promote `on-demand`
tools (`core/lifecycle_scanner._classify_promotion`) — `on-demand →
loaded-on-boot` stays a legal *manual* transition, but autonomous
promotion would silently undo the operator's deliberate off-boot
decision and is skipped.

Transition validation lives in `core/tool_transitions.py`.
"""


PIN_STATUS_VALUES = (
    "always-pinned",
    "auto-managed",
)
"""Operator-pin authority class for a tool's residence in
`loaded-on-boot` (DECISIONS D77).

- `always-pinned` — stays in `loaded-on-boot` regardless of usage
  telemetry. Concierge's autonomous lifecycle logic may not demote it,
  flag it for retirement on a usage signal, or transition it out of
  `loaded-on-boot`. Only the operator removes the pin. The canonical
  case is a tool whose value is invisible to usage telemetry (e.g.
  Alfred's semantic-memory MCP — always used by necessity, never
  tripping usage counters).
- `auto-managed` — in `loaded-on-boot` but Concierge-managed; usage
  telemetry drives its fate. The default for every row.

Pin status is a property of the tool's *current residence* in
`loaded-on-boot`, not a permanent property — re-promotion after a
demotion is a fresh decision (D77). It is meaningful only for
`loaded-on-boot` rows; non-boot rows carry the `auto-managed` default
inertly.

Like `LIFECYCLE_STATE_VALUES` / `TOOL_TYPE_VALUES`, this value set is
enforced Python-side only: the SQLAlchemy `Enum` built from it renders
as a plain `VARCHAR` in SQLite with **no CHECK constraint**
(`create_constraint` defaults False, not overridden). A dedicated
follow-on slice hardens all three Enum columns with
`create_constraint=True` together (see the Stage 1B reconciliation +
pin-status DECISIONS bundle).
"""


USAGE_EVENT_TYPE_VALUES = (
    "recommended",
    "installed",
    "loaded",
    "used",
    "removed",
)
"""ToolUsageEvent.event_type enum — the five kinds of per-tool telemetry
the §C7 promotion/demotion scanner aggregates over.

Emit hooks wire in Fix Day 3 (`concierge_recommend`, `install_by_method`,
loader `load()`). This revision only lands the table so the schema is
ready to accept writes. CHECK-constraint + Python-level enum validation
keeps the value set tight — scanner aggregation queries assume these
exact five event_type labels.
"""


class Pack(Base):
    __tablename__ = "packs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transport: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    tools: Mapped[list["Tool"]] = relationship(
        back_populates="pack", cascade="all, delete-orphan"
    )


class Tool(Base):
    __tablename__ = "tools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pack_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("packs.id"), nullable=True, index=True
    )
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_type: Mapped[Optional[str]] = mapped_column(
        Enum(*TOOL_TYPE_VALUES, name="tool_type"),
        nullable=True,
        index=True,
    )
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    install_method: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    install_method_provenance: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )
    is_in_manifest: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    lifecycle_state: Mapped[str] = mapped_column(
        Enum(*LIFECYCLE_STATE_VALUES, name="lifecycle_state"),
        nullable=False,
        default="discovered",
        server_default="discovered",
        index=True,
    )
    # Operator-pin authority class (DECISIONS D77). Meaningful for
    # rows residing in `loaded-on-boot`; every other row carries the
    # `auto-managed` default inertly. NOT-NULL with a server_default
    # so the column has a value on every row including the existing
    # catalog (the add-column migration backfills via the default).
    # `Enum`-typed at the model layer but — like `lifecycle_state` /
    # `tool_type` — enforced Python-side only: no DB CHECK constraint
    # until the dedicated Enum-hardening follow-on slice.
    pin_status: Mapped[str] = mapped_column(
        Enum(*PIN_STATUS_VALUES, name="pin_status"),
        nullable=False,
        default="auto-managed",
        server_default="auto-managed",
        index=True,
    )
    # Skills-specific fields (tool_type='skill'). Both nullable for
    # non-skill rows: `path` has no analogue for MCP/CLI/HTTP, and
    # `ambient_loading` is a skills-only concept (loaded-into-context
    # whenever the SKILL.md's trigger conditions match, vs. MCP which
    # is explicitly loaded into a session).
    path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    ambient_loading: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True
    )
    # Catalog metadata extension (Stage 1A items 4+7). All nullable —
    # populated by `scripts/ingest_tool_manifest.py` from the live
    # TOOL-MANIFEST.md, NULL for rows that predate the ingest or for
    # tools whose manifest entries don't carry the field. `transport`
    # exists separately on Pack already; per-tool `transport` here is
    # a different concern (per-tool override / non-MCP transport).
    # `succeeded_by` is a plain slug reference, not a foreign key —
    # retirement lineage is informational for the recommendation
    # engine, not a structural constraint.
    agent_owner: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    best_for: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    limitation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prefix: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    transport: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    auth: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    succeeded_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    pack: Mapped[Optional[Pack]] = relationship(back_populates="tools")


class Request(Base):
    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    folder: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    tool_name: Mapped[str] = mapped_column(String(256))
    tool_slug: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    confidence: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    is_discovered: Mapped[bool] = mapped_column(Boolean, default=False)
    # Stage 1A item 5 — worker-to-Alfred escalation routing. NULL means
    # "no escalation target" (default for Alfred-form filings and
    # backward-compat with pre-item-5 rows). Allowed non-NULL values
    # per ESCALATION_TARGET_VALUES in core/lifecycle_store/escalation.py
    # ({"alfred", "operator"}); validation lives at the Pydantic Literal
    # on the API query parameter + the NewRequestDraft schema. Indexed
    # for the `GET /requests/pending?escalation_target=alfred` filter
    # (Alfred-facing review queue lookup).
    escalation_target: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True, index=True
    )
    raw_markdown: Mapped[str] = mapped_column(Text)
    parsed_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class MemoryEvent(Base):
    __tablename__ = "memory_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ToolUsageEvent(Base):
    __tablename__ = "tool_usage_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tool_id: Mapped[int] = mapped_column(
        ForeignKey("tools.id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(
        Enum(*USAGE_EVENT_TYPE_VALUES, name="usage_event_type"),
        nullable=False,
        index=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )
    session_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, index=True
    )
    context: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
