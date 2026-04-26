"""GET /tools endpoints — list with filters + by-id fetch."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from core.api.schemas import ToolList, ToolOut
from core.db.models import Tool
from core.db.session import get_db

router = APIRouter(prefix="/tools", tags=["tools"])


def _escape_like(s: str) -> str:
    """Escape SQL LIKE wildcards (`%` and `_`) and the escape char
    itself in user input so they're treated as literal characters.
    Used by the `name_q` filter (Day 10 Task 2) so an operator typing
    `_legacy` or `100%` doesn't accidentally match wildcards.
    """
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _to_out(tool: Tool) -> ToolOut:
    return ToolOut(
        id=tool.id,
        slug=tool.slug,
        name=tool.name,
        description=tool.description,
        tool_type=tool.tool_type,
        category=tool.category,
        install_method=tool.install_method,
        is_in_manifest=tool.is_in_manifest,
        is_active=tool.is_active,
        lifecycle_state=tool.lifecycle_state,
        path=tool.path,
        ambient_loading=tool.ambient_loading,
        pack_id=tool.pack_id,
        pack_slug=tool.pack.slug if tool.pack else None,
        pack_name=tool.pack.name if tool.pack else None,
        created_at=tool.created_at,
        updated_at=tool.updated_at,
    )


@router.get("", response_model=ToolList)
def list_tools(
    pack_id: Optional[int] = Query(None),
    pack_slug: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    is_in_manifest: Optional[bool] = Query(None),
    dormant: Optional[bool] = Query(
        None,
        description="Convenience filter: is_in_manifest=True AND is_active=False",
    ),
    category: Optional[str] = Query(None),
    tool_type: Optional[str] = Query(None),
    slug: Optional[str] = Query(None),
    name_q: Optional[str] = Query(
        None,
        description=(
            "Free-text substring search across `Tool.name` OR "
            "`Tool.slug`, case-insensitive. Empty / whitespace-only "
            "input is treated as no-filter. Wildcards (`%`, `_`) are "
            "escaped pre-LIKE so operator input matches literally."
        ),
    ),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> ToolList:
    query = db.query(Tool).options(joinedload(Tool.pack))

    if pack_id is not None:
        query = query.filter(Tool.pack_id == pack_id)
    if pack_slug is not None:
        from core.db.models import Pack

        query = query.join(Pack, Tool.pack_id == Pack.id).filter(Pack.slug == pack_slug)
    if is_active is not None:
        query = query.filter(Tool.is_active.is_(is_active))
    if is_in_manifest is not None:
        query = query.filter(Tool.is_in_manifest.is_(is_in_manifest))
    if dormant is True:
        query = query.filter(
            Tool.is_in_manifest.is_(True), Tool.is_active.is_(False)
        )
    elif dormant is False:
        query = query.filter(
            ~(Tool.is_in_manifest.is_(True) & Tool.is_active.is_(False))
        )
    if category is not None:
        query = query.filter(Tool.category == category)
    if tool_type is not None:
        query = query.filter(Tool.tool_type == tool_type)
    if slug is not None:
        query = query.filter(Tool.slug == slug)
    if name_q and name_q.strip():
        # Day 10 Task 2 alignment: name OR slug substring match,
        # case-insensitive ilike, with `.distinct()` belt-and-
        # suspenders against double-matches when a row's name and
        # slug both match the same pattern. Wildcard escape keeps
        # operator input literal.
        escaped = _escape_like(name_q.strip())
        pattern = f"%{escaped}%"
        query = query.filter(
            or_(
                Tool.name.ilike(pattern, escape="\\"),
                Tool.slug.ilike(pattern, escape="\\"),
            )
        ).distinct()

    total = query.count()
    rows = query.order_by(Tool.id).offset(offset).limit(limit).all()
    return ToolList(items=[_to_out(t) for t in rows], total=total)


@router.get("/{tool_id}", response_model=ToolOut)
def get_tool(tool_id: int, db: Session = Depends(get_db)) -> ToolOut:
    tool = (
        db.query(Tool)
        .options(joinedload(Tool.pack))
        .filter(Tool.id == tool_id)
        .one_or_none()
    )
    if tool is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tool not found")
    return _to_out(tool)
