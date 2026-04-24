"""End-to-end integration: request → event → install → scanner → promotion.

Fix Day 4 Task 7 — one big test that exercises the full Tier 1+2
pipeline in one go:

  1. File a request via `LifecycleService.create_request`
  2. Assert the broker publishes a `new_request` event to subscribers
  3. Approve via `update_status(status=approved)`
  4. Assert the stubbed install dispatcher runs and emits an
     `installed` ToolUsageEvent
  5. Seed PROMOTION_MIN_USES additional `recommended` events to
     cross the promotion threshold
  6. Call `lifecycle_scanner.run_once` directly (not the weekly
     scheduler — deterministic) and assert the tool auto-promotes
  7. Assert identity refresh was triggered by the loaded-on-boot
     transition (via FakeMemory's `identity_set` capture)

**Why call run_once directly instead of hitting /scanner/run?**
Per the Fix Day 4 session plan: APScheduler + HTTP + async + SSE
in one test creates cancellation-timing flakiness; `run_once` is
the same code path the scheduler + HTTP endpoint both call. Direct
invocation keeps the assertion crisp.

**Memory stub.** The identity-refresh hook needs a MemoryClient;
using the real ChromaDB adds boot cost. The FakeMemory captures
`identity_set` calls so we can assert the refresh fired without
spinning up ChromaDB.
"""
from __future__ import annotations

import asyncio
from contextlib import aclosing
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from core.db.models import Tool, ToolUsageEvent
from core.events import EventBroker
from core.identity import refresh_identity_on_loaded_on_boot_change
from core.lifecycle_policy import PROMOTION_MIN_USES
from core.lifecycle_scanner import run_once
from core.lifecycle_store.schema import NewRequestDraft, StatusChange
from core.lifecycle_store.service import LifecycleService
from core.tool_transitions import transition_tool_lifecycle


# ---- Fakes -------------------------------------------------------------


@dataclass
class FakeMemory:
    """Capture identity_set calls; return the stored text on
    identity_get. Matches the subset of MemoryClient the scanner's
    identity refresh hook exercises.
    """

    identity_store: dict[str, str] = field(default_factory=dict)
    set_calls: list[tuple[str, str]] = field(default_factory=list)

    def identity_set(self, text: str, *, key: str = "primary") -> None:
        self.identity_store[key] = text
        self.set_calls.append((key, text))

    def identity_get(self, *, key: str = "primary") -> str:
        return self.identity_store.get(key, "")


@pytest.fixture
def lifecycle_root(tmp_path) -> Path:
    for folder in ("pending", "resolved", "archived"):
        (tmp_path / folder).mkdir()
    return tmp_path


def _stub_install_dispatcher(success: bool = True):
    """Build an install-dispatcher stub that pretends the install
    succeeded (or failed). Deterministic — no subprocess.
    """
    from core.install import InstallResult

    def dispatcher(method, *, tool_name, **kwargs):
        # Normalized method names live on the result ("pip_user", not
        # "pip-user"). The service layer uses result.method for the
        # telemetry event's install_method field.
        return InstallResult(
            method="pip_user",
            command=f"pip install --user {tool_name}",
            success=success,
            returncode=0 if success else 1,
            stdout="stubbed",
            stderr="",
            elapsed_ms=42,
        )

    return dispatcher


# ---- Integration test --------------------------------------------------


class TestFullCycle:
    @pytest.mark.asyncio
    async def test_request_event_install_scanner_promotion_identity(
        self, db_session: Session, lifecycle_root: Path
    ):
        """The full Tier 1+2 cycle in one pass.

        Pins the integration contract between:
        - service.create_request → broker.publish (Task 4)
        - service.approve-triggers-install → telemetry emit (Task 6)
        - scanner.run_once → lifecycle transition (Task 5)
        - transition hook → identity refresh (Fix Day 3 Fork 5)
        """
        # ---- setup -----------------------------------------------
        broker = EventBroker()
        memory = FakeMemory()
        svc = LifecycleService(
            session=db_session,
            lifecycle_root=lifecycle_root,
            install_dispatcher=_stub_install_dispatcher(success=True),
            event_broker=broker,
        )

        # Seed the catalog row the install will target. The
        # scanner's promotion path looks up by Tool.slug; without
        # this row nothing to promote.
        db_session.add(
            Tool(
                slug="csvkit",
                name="csvkit",
                tool_type="cli",
                lifecycle_state="discovered",
            )
        )
        db_session.commit()

        # ---- 1+2: create_request + broker fires new_request ------
        received_events: list[dict] = []

        async def broker_consumer():
            async with aclosing(broker.subscribe()) as gen:
                async for event in gen:
                    received_events.append(event)
                    break

        consumer_task = asyncio.create_task(broker_consumer())
        await asyncio.sleep(0)

        draft = NewRequestDraft(
            tool_name="csvkit",
            install_method="pip-user",
            task_context="end-to-end cycle test",
            confidence="high",
        )
        detail = svc.create_request(draft)

        await asyncio.wait_for(consumer_task, timeout=2.0)
        assert len(received_events) == 1
        assert received_events[0]["event"] == "new_request"
        assert received_events[0]["data"]["filename"] == detail.filename

        # ---- 3+4: approve + install fires ToolUsageEvent ---------
        approve_result = svc.update_status(
            filename=detail.filename,
            change=StatusChange(
                status="approved",
                session_id="integration-test-session",
            ),
        )
        assert approve_result.status == "installed"

        install_events = (
            db_session.query(ToolUsageEvent)
            .filter(ToolUsageEvent.event_type == "installed")
            .all()
        )
        assert len(install_events) == 1
        assert install_events[0].session_id == "integration-test-session"

        # ---- 5: seed promotion-signal events over the window ----
        # Auto-promote needs install-age ≥ 30 days. The tool row was
        # just created; nudge created_at back to simulate an older
        # catalog entry. Raw-SQL bypasses the transition listener,
        # which is desired here — we're editing a non-lifecycle
        # column.
        from sqlalchemy import text
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=60)
        db_session.execute(
            text("UPDATE tools SET created_at = :ts WHERE slug = 'csvkit'"),
            {"ts": past},
        )

        tool = db_session.query(Tool).filter_by(slug="csvkit").one()
        for _ in range(PROMOTION_MIN_USES):
            db_session.add(
                ToolUsageEvent(
                    tool_id=tool.id,
                    event_type="recommended",
                    timestamp=now - timedelta(days=3),
                )
            )
        db_session.commit()

        # ---- 6: scanner.run_once auto-promotes ------------------
        summary = run_once(db_session, memory=memory, now=now)
        db_session.commit()

        assert "csvkit" in summary.auto_promoted
        db_session.refresh(tool)
        assert tool.lifecycle_state == "loaded-on-boot"

        # ---- 7: identity refresh fired -------------------------
        # refresh_identity_on_loaded_on_boot_change must have been
        # called by the scanner's on_transition hook, which calls
        # identity_set on the FakeMemory.
        assert len(memory.set_calls) >= 1
        latest = memory.identity_get()
        assert "csvkit" in latest, (
            f"identity text should mention the newly-promoted tool; got: {latest!r}"
        )

    @pytest.mark.asyncio
    async def test_cycle_survives_no_memory_client(
        self, db_session: Session, lifecycle_root: Path
    ):
        """If no memory client is wired into the scanner, the cycle
        still completes — auto-promotion fires, identity refresh is
        skipped. Matches the Fix Day 3 graceful-degradation posture.
        """
        broker = EventBroker()
        svc = LifecycleService(
            session=db_session,
            lifecycle_root=lifecycle_root,
            install_dispatcher=_stub_install_dispatcher(success=True),
            event_broker=broker,
        )

        db_session.add(
            Tool(
                slug="no-mem-tool",
                name="no-mem-tool",
                tool_type="cli",
                lifecycle_state="used",
            )
        )
        db_session.commit()

        from sqlalchemy import text
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=60)
        db_session.execute(
            text("UPDATE tools SET created_at = :ts WHERE slug = 'no-mem-tool'"),
            {"ts": past},
        )
        tool = db_session.query(Tool).filter_by(slug="no-mem-tool").one()
        for _ in range(PROMOTION_MIN_USES):
            db_session.add(
                ToolUsageEvent(
                    tool_id=tool.id,
                    event_type="recommended",
                    timestamp=now - timedelta(days=3),
                )
            )
        db_session.commit()

        # memory=None — identity refresh should silently skip.
        summary = run_once(db_session, memory=None, now=now)
        db_session.commit()

        assert "no-mem-tool" in summary.auto_promoted
        db_session.refresh(tool)
        assert tool.lifecycle_state == "loaded-on-boot"
