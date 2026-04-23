"""FastAPI application factory."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.api import health, packs, recommend, requests as requests_api, tools
from core.config import get_settings
from core.db.session import ensure_schema_current, get_session_factory
from core.lifecycle_store.store import reconcile as reconcile_lifecycle
from core.logging import configure_logging
from core.recommend.counters import log_shutdown_summary

logger = logging.getLogger("concierge")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    ensure_schema_current()
    logger.info(
        "Concierge starting (env=%s debug=%s db=%s model=%s effort=%s "
        "lifecycle_root=%s)",
        settings.env,
        settings.debug,
        settings.database_path,
        settings.anthropic_model,
        settings.claude_code_recommend_effort,
        settings.lifecycle_root,
    )
    # N7 lifespan reconciliation — one DB/filesystem sync pass at
    # startup so `GET /requests/pending` is a fast query on a
    # populated DB. Unparseable files are logged as WARNING (by the
    # store) but do not block startup.
    session = get_session_factory()()
    try:
        stats = reconcile_lifecycle(session, settings.lifecycle_root)
        logger.info(
            "lifecycle.reconcile.done scanned=%d inserted=%d updated=%d unparseable=%d "
            "root=%s",
            stats.scanned,
            stats.inserted,
            stats.updated,
            stats.unparseable,
            settings.lifecycle_root,
        )
    finally:
        session.close()
    yield
    # Session-level recommendation summary — load-bearing for the
    # 48h operational-shakedown gate per DECISIONS [2026-04-21 18:00].
    log_shutdown_summary()
    logger.info("Concierge shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Concierge",
        description="Platform-agnostic tool awareness layer for AI agents",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.include_router(health.router)
    app.include_router(tools.router)
    app.include_router(packs.router)
    app.include_router(recommend.router)
    app.include_router(requests_api.router)

    return app


app = create_app()
