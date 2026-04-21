"""GET /packs endpoint — list packs with per-pack tool counts."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.api.schemas import PackList, PackOut
from core.db.models import Pack, Tool
from core.db.session import get_db

router = APIRouter(prefix="/packs", tags=["packs"])


@router.get("", response_model=PackList)
def list_packs(
    status: Optional[str] = Query(None),
    transport: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> PackList:
    base = db.query(Pack)
    if status is not None:
        base = base.filter(Pack.status == status)
    if transport is not None:
        base = base.filter(Pack.transport == transport)

    total = base.count()
    rows = base.order_by(Pack.id).offset(offset).limit(limit).all()

    counts = dict(
        db.query(Tool.pack_id, func.count(Tool.id))
        .filter(Tool.pack_id.isnot(None))
        .group_by(Tool.pack_id)
        .all()
    )

    items = [
        PackOut(
            id=p.id,
            slug=p.slug,
            name=p.name,
            description=p.description,
            transport=p.transport,
            status=p.status,
            tool_count=counts.get(p.id, 0),
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in rows
    ]
    return PackList(items=items, total=total)
