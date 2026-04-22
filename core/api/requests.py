"""POST /requests, GET /requests/pending, GET /requests/{id},
POST /requests/{id}/status — the N7 HTTP surface.

Thin router over `core.lifecycle_store.service.LifecycleService`.
Error-class translation mirrors the N6 router's discipline: each
service-level exception maps to a distinct HTTP status + structured
detail body so soak-log readers can distinguish failure modes at
a glance.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.config import Settings, get_settings
from core.db.session import get_db
from core.lifecycle_store.schema import (
    ListedRequest,
    NewRequestDraft,
    RequestDetail,
    StatusChange,
)
from core.lifecycle_store.service import (
    LifecycleService,
    RequestNotFoundError,
)
from core.lifecycle_store.transitions import InvalidTransitionError


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/requests", tags=["requests"])


def get_lifecycle_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LifecycleService:
    return LifecycleService(session=db, lifecycle_root=settings.lifecycle_root)


class PendingListResponse(BaseModel):
    """Envelope over the listed-request list so the API can grow
    (counts, cursor, etc.) without breaking callers.
    """

    items: list[ListedRequest]
    total: int


@router.post("", response_model=RequestDetail, status_code=status.HTTP_201_CREATED)
def create_request(
    draft: NewRequestDraft,
    service: LifecycleService = Depends(get_lifecycle_service),
) -> RequestDetail:
    try:
        return service.create_request(draft)
    except FileExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "request_filename_collision",
                "message": str(exc),
            },
        )


@router.get("/pending", response_model=PendingListResponse)
def list_pending(
    stale: bool = Query(False, description="Filter to files older than STALE_PENDING_DAYS."),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    service: LifecycleService = Depends(get_lifecycle_service),
) -> PendingListResponse:
    items = service.list_pending(stale=stale, limit=limit, offset=offset)
    return PendingListResponse(items=items, total=len(items))


@router.get("/{request_id}", response_model=RequestDetail)
def get_request(
    request_id: int,
    service: LifecycleService = Depends(get_lifecycle_service),
) -> RequestDetail:
    detail = service.get_request(request_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "request_not_found", "message": f"id={request_id}"},
        )
    return detail


@router.post(
    "/{filename}/status", response_model=RequestDetail
)
def update_status(
    filename: str,
    change: StatusChange,
    service: LifecycleService = Depends(get_lifecycle_service),
) -> RequestDetail:
    try:
        return service.update_status(filename=filename, change=change)
    except RequestNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "request_not_found", "message": str(exc)},
        )
    except InvalidTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "invalid_transition", "message": str(exc)},
        )
