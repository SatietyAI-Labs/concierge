"""POST /recommend — the N6 endpoint.

Thin HTTP adapter over `core.recommend.service.RecommendationService`.
Owns three concerns:

1. **Dependency wiring**: construct the service with its three
   dependencies (memory client, Anthropic client, catalog fetcher).
   The service itself is agnostic to where those come from; the
   router provides the FastAPI-idiomatic wiring.
2. **Error-class translation**: memory outages are fielded inside
   the service and surface as a normal 200 response with
   `memory_available=False`. Parse failures and Anthropic client
   errors are distinct failure classes that the service re-raises;
   this router translates them to structured 502s so the
   operational-first log surface at the HTTP layer stays
   readable.
3. **Catalog fetcher scope**: the SQLite snapshot is taken at
   request time (per request, not cached) so any catalog edits
   from the cron or UI land in the next recommendation without a
   service restart.
"""
from __future__ import annotations

import logging
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from core.config import Settings, get_settings
from core.db.models import Tool
from core.db.session import get_db
from core.memory import MemoryClient, get_memory_client
from core.recommend.client import AnthropicClientError, AnthropicRecommender
from core.recommend.parse import RecommendationParseError
from core.recommend.prompt import CatalogToolView
from core.recommend.schemas import RecommendRequest, RecommendResponse
from core.recommend.service import RecommendationService
from core.telemetry import make_db_sink


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommend", tags=["recommend"])


# ---- Dependency factories ------------------------------------------------


def _catalog_view(tool: Tool) -> CatalogToolView:
    return CatalogToolView(
        slug=tool.slug,
        name=tool.name,
        description=tool.description,
        category=tool.category,
        pack_slug=tool.pack.slug if tool.pack else None,
        is_in_manifest=tool.is_in_manifest,
        tool_type=tool.tool_type,
        install_method=tool.install_method,
        path=tool.path,
        ambient_loading=tool.ambient_loading,
        lifecycle_state=tool.lifecycle_state,
    )


def _make_catalog_fetcher(db: Session):
    """Build a zero-arg closure that reads a catalog snapshot from
    the provided session. The closure captures `db`; FastAPI owns
    the session lifetime via `get_db`, so the closure is only ever
    invoked inside the request handler where `db` is live.
    """

    def fetch() -> Iterable[CatalogToolView]:
        rows = db.query(Tool).options(joinedload(Tool.pack)).all()
        return [_catalog_view(t) for t in rows]

    return fetch


def get_anthropic_recommender(
    settings: Settings = Depends(get_settings),
) -> AnthropicRecommender:
    """Per-request AnthropicRecommender. Construction is cheap (no
    SDK init) and the Messages client is lazy-initialized on first
    `.call(...)` per `client.py`; building a fresh wrapper each
    request keeps settings overrides (especially the effort
    override via CONCIERGE_RECOMMEND_EFFORT) responsive without a
    process restart.
    """
    api_key = (
        settings.anthropic_api_key.get_secret_value()
        if settings.anthropic_api_key
        else None
    )
    return AnthropicRecommender(
        api_key=api_key,
        model=settings.anthropic_model,
        effort=settings.claude_code_recommend_effort,
        max_tokens=settings.recommend_max_tokens,
    )


def get_recommendation_service(
    db: Session = Depends(get_db),
    memory: MemoryClient = Depends(get_memory_client),
    anthropic: AnthropicRecommender = Depends(get_anthropic_recommender),
    settings: Settings = Depends(get_settings),
) -> RecommendationService:
    return RecommendationService(
        memory=memory,
        anthropic=anthropic,
        fetch_catalog=_make_catalog_fetcher(db),
        memory_search_limit=settings.recommend_memory_search_limit,
        emit_usage=make_db_sink(db),
    )


# ---- Endpoint ------------------------------------------------------------


@router.post("", response_model=RecommendResponse)
def recommend(
    req: RecommendRequest,
    service: RecommendationService = Depends(get_recommendation_service),
    db: Session = Depends(get_db),
) -> RecommendResponse:
    try:
        response = service.recommend(req)
        # `make_db_sink` adds + flushes per-rec `ToolUsageEvent` rows
        # but explicitly does not commit (see `core/telemetry.py`
        # docstring — "caller owns the transaction"). Without the
        # commit here, `get_db`'s `finally`-close rolls back the
        # implicit transaction and the flushed telemetry rows are
        # discarded — the Fix Day 5 bug captured in Appendix D of
        # `SESSION-2026-04-25-03.md`. The install path commits via
        # the lifecycle-store update_status downstream; the recommend
        # path has no downstream commit, so it owns the boundary
        # itself.
        db.commit()
        return response
    except RecommendationParseError as exc:
        # Service has already logged ERROR with
        # `recommend.parse_failed`; the HTTP boundary adds a
        # structured body distinct from an Anthropic-level failure.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "recommendation_parse_failed",
                "message": str(exc),
            },
        )
    except AnthropicClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "anthropic_client_failed",
                "message": str(exc),
            },
        )
