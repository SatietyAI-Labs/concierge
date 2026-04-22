"""FastAPI application factory."""
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from core.api import packs, recommend, tools
from core.config import Settings, get_settings
from core.db.session import init_db
from core.logging import configure_logging
from core.recommend.counters import log_shutdown_summary

logger = logging.getLogger("concierge")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    init_db()
    logger.info(
        "Concierge starting (env=%s debug=%s db=%s model=%s temperature=%s)",
        settings.env,
        settings.debug,
        settings.database_path,
        settings.anthropic_model,
        settings.recommend_temperature,
    )
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

    @app.get("/health")
    def health(settings: Settings = Depends(get_settings)):
        return {"status": "ok", "env": settings.env, "version": "0.1.0"}

    app.include_router(tools.router)
    app.include_router(packs.router)
    app.include_router(recommend.router)

    return app


app = create_app()
