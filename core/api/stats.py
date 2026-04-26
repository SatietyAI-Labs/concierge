"""GET /stats/* — operator-facing aggregations for the dashboard
Health/Stats bar.

## /stats/top-tools

Top-3 tools by recommendation count, all-time, filtered on
`tool_usage_events.event_type='recommended'`.

Per Day 10 Task 1 Step 2 surface (DECISIONS `[2026-05-01 Day 10]`),
`recommended` is the only `tool_usage_events.event_type` with
meaningful per-tool population today — `installed` is one-off-per-
tool (no ranking signal); `loaded` and `used` emit-wiring is deferred
(see `core/telemetry.py:21-24`). When `used` event-wiring lands, the
filter here should switch from `recommended` to `used` for a truer
"most-used" signal — one-line change, no schema or UI impact.

Field naming `times_recommended` chosen over `recommendation_count`
to read more naturally in operator context ("ripgrep — times
recommended: 47") and stay unambiguous about what's measured.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.db.models import Tool, ToolUsageEvent
from core.db.session import get_db


router = APIRouter(prefix="/stats", tags=["stats"])


class TopToolEntry(BaseModel):
    slug: str
    name: str
    times_recommended: int = Field(
        description=(
            "Count of `tool_usage_events.event_type='recommended'` rows "
            "joined to this tool, all-time."
        ),
    )


class TopToolsResponse(BaseModel):
    items: List[TopToolEntry]


@router.get("/top-tools", response_model=TopToolsResponse)
def top_tools(db: Session = Depends(get_db)) -> TopToolsResponse:
    """Top-3 most-recommended tools, all-time. Returns 200 + empty
    list for fresh installs / no-recommendations-yet state — UI
    handles empty rendering separately via the dashboard's
    designed-empty-state philosophy.
    """
    rows = (
        db.query(
            Tool.slug,
            Tool.name,
            func.count(ToolUsageEvent.id).label("times_recommended"),
        )
        .join(Tool, ToolUsageEvent.tool_id == Tool.id)
        .filter(ToolUsageEvent.event_type == "recommended")
        .group_by(Tool.id, Tool.slug, Tool.name)
        .order_by(func.count(ToolUsageEvent.id).desc())
        .limit(3)
        .all()
    )
    return TopToolsResponse(
        items=[
            TopToolEntry(slug=slug, name=name, times_recommended=count)
            for (slug, name, count) in rows
        ]
    )
