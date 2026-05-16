"""FastAPI application factory."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from core.api import (
    events as events_api,
    health,
    packs,
    recommend,
    requests as requests_api,
    scanner as scanner_api,
    stats,
    tools,
)
from core.config import get_settings
from core.db.session import ensure_schema_current, get_session_factory
from core.events import EventBroker
from core.lifecycle_scanner import run_once as scanner_run_once
from core.lifecycle_store.store import reconcile as reconcile_lifecycle
from core.logging import configure_logging
from core.memory import MemoryUnavailableError, get_memory_client
from core.recommend.counters import log_shutdown_summary

logger = logging.getLogger("concierge")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    ensure_schema_current()
    # Fix Day 4 Task 4 — per-app singleton EventBroker on app.state.
    # Service construction (`get_lifecycle_service`) and the SSE
    # endpoint (`get_event_broker`) both read it from here so the
    # broker is shared across all requests on this process.
    app.state.event_broker = EventBroker()
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

    # Fix Day 4 Task 5 — promotion/demotion scanner via APScheduler
    # (not cron per DECISIONS [2026-04-23]). The `last_scanner_summary`
    # starts None; `/health` tolerates that until the first run
    # completes.
    #
    # SHAKEDOWN CADENCE: daily at 03:00 local during the 48h
    # operational-shakedown window so the scanner actually fires
    # inside the soak period. Steady-state weekly cadence (the
    # originally-designed Sunday-03:00 frequency per `## Weekly review`
    # in the tool-lifecycle skill) is restored post-soak — revert this
    # trigger back to `day_of_week="sun"` once the shakedown gate is
    # cleared. Day 5 today.md carries the revert as a checklist item.
    app.state.last_scanner_summary = None
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _run_scheduled_scan,
        trigger=CronTrigger(hour=3, minute=0),  # daily during shakedown; revert to day_of_week="sun" post-soak
        args=[app],
        id="concierge.weekly_scanner",
        name="Concierge promotion/demotion scan (daily during shakedown)",
        replace_existing=True,
    )
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info("scheduler.started weekly_scanner=concierge.weekly_scanner")

    # §VIII.2 / D88 — cold-start pre-warm. Schedule a background task
    # that pays the ChromaDB + sentence-transformers warmup tax
    # (~34–55s) off the request path, so an agent's first /recommend
    # call hits an already-warm memory client instead of hanging.
    # Non-blocking: lifespan yields immediately and /health stays
    # responsive while warmup runs in a worker thread. The §VIII.2
    # literal "no-op /memory/search call ~10s after uvicorn comes up"
    # is errata — there is no /memory/* HTTP endpoint (D84 F1); the
    # in-process MemoryClient call here is the correct mechanism, and
    # a background task scheduled at lifespan-yield is already "after
    # uvicorn comes up" with no artificial delay needed. Disabled via
    # CONCIERGE_PREWARM_ON_STARTUP=false (the test suite sets this).
    if settings.prewarm_on_startup:
        # Strong reference on app.state — asyncio holds only a weak
        # ref to tasks; without this the task could be GC'd mid-warmup.
        app.state.prewarm_task = asyncio.create_task(_prewarm_memory())
        logger.info("memory.prewarm.scheduled")
    else:
        app.state.prewarm_task = None
        logger.info("memory.prewarm.disabled")

    yield

    # Teardown — stop the scheduler before the event loop winds down
    # so in-flight jobs get a clean cancellation rather than a
    # traceback at exit.
    try:
        scheduler.shutdown(wait=False)
        logger.info("scheduler.stopped")
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("scheduler.shutdown_failed error=%s", exc)

    # Cancel an in-flight pre-warm task — relevant for short-lived
    # lifespans (e.g. test TestClient contexts) that exit before
    # warmup completes, so the task does not outlive the event loop
    # as a dangling pending task.
    prewarm_task = getattr(app.state, "prewarm_task", None)
    if prewarm_task is not None and not prewarm_task.done():
        prewarm_task.cancel()
        logger.info("memory.prewarm.cancelled")

    # Session-level recommendation summary — load-bearing for the
    # 48h operational-shakedown gate per DECISIONS [2026-04-21 18:00].
    log_shutdown_summary()
    logger.info("Concierge shutting down")


def _run_scheduled_scan(app: FastAPI) -> None:
    """APScheduler job entrypoint — opens a short-lived session,
    runs one scan, commits, stores the summary on `app.state`.

    Synchronous on purpose: APScheduler's AsyncIOScheduler can run
    sync jobs on its own thread-pool, and the scanner + DB session
    are sync. Makes commit semantics crisp.
    """
    session = get_session_factory()()
    try:
        summary = scanner_run_once(
            session,
            memory=getattr(app.state, "memory", None),
        )
        session.commit()
        app.state.last_scanner_summary = summary
        logger.info(
            "scheduler.scan_complete auto_promoted=%d promotion_candidates=%d "
            "demotion_candidates=%d stale_pending=%d errors=%d",
            len(summary.auto_promoted),
            len(summary.promotion_candidates),
            len(summary.demotion_candidates),
            len(summary.stale_pending),
            len(summary.errors),
        )
    except Exception as exc:
        logger.exception("scheduler.scan_failed error=%s", exc)
        session.rollback()
    finally:
        session.close()


async def _prewarm_memory() -> None:
    """Background task — pays the MemoryClient warmup tax off the
    request path (§VIII.2 / D88).

    Warms the `get_memory_client()` process singleton — the exact
    instance the `/recommend` endpoint resolves via DI — so Scout's
    first `concierge_recommend` call at Gate 4 hits a warm client.
    The blocking `prewarm()` runs in a worker thread so the event
    loop keeps serving requests during the ~34–55s warmup.

    Failure is swallowed with a WARN: a memory-store problem must
    never crash service startup. The `/recommend` path has its own
    graceful degradation (`MemoryUnavailableError` → recommendation
    without memory context), so a failed pre-warm is no worse than
    the pre-D88 status quo — it just means the tax is paid later, on
    a real call, exactly as it was before this hook existed.
    """
    try:
        client = get_memory_client()
        await asyncio.to_thread(client.prewarm)
        logger.info("memory.prewarm.done")
    except MemoryUnavailableError as exc:
        logger.warning("memory.prewarm.unavailable error=%s", exc)
    except asyncio.CancelledError:
        # Lifespan teardown cancelled an in-flight warmup — expected
        # for short-lived lifespans; re-raise so the task settles as
        # cancelled rather than as a swallowed error.
        raise
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("memory.prewarm.unexpected_error error=%s", exc)


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
    app.include_router(events_api.router)
    app.include_router(scanner_api.router)
    app.include_router(stats.router)

    return app
