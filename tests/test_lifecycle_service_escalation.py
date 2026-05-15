"""Integration tests for Stage 1A item 5 escalation routing through
the lifecycle service, writer, ingest, and DB layers.

Covers the full surface that lands when a worker-form filing flows
through `LifecycleService.create_request`:

1. `Request.escalation_target` column persists and surfaces on
   RequestDetail.
2. Filename gets the `worker-<name>-` prefix when agent_id names a
   worker; bare slug otherwise (Alfred-form backward compat).
3. Worker-form `parsed_data` carries the `escalation` section with
   the right keys (`worker`, `gap`, `workaround_used`).
4. Rendered markdown contains an `## Escalation` section between
   `## Request` and `## Recommendation` (Option β H1 unification).
5. **Backward-compat invariant** — Alfred-form drafts produce
   byte-identical output to a known-good template, verified through
   round-trip parse + emit, ensuring item 5's writer extension
   didn't drift the existing rendering shape (operator watch item).
6. Category-agnostic — skill-request worker form round-trips
   correctly with no MCP-shape assumptions in any output.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from core.db.models import Request
from core.ingest.tool_requests import parse_request_file
from core.lifecycle_store.schema import NewRequestDraft
from core.lifecycle_store.service import (
    LifecycleCounters,
    LifecycleService,
    reset_counters_for_tests,
)
from core.lifecycle_store.writer import build_markdown


@pytest.fixture
def lifecycle_root(tmp_path) -> Path:
    for folder in ("pending", "resolved", "archived"):
        (tmp_path / folder).mkdir()
    return tmp_path


@pytest.fixture
def service(db_session: Session, lifecycle_root: Path) -> LifecycleService:
    reset_counters_for_tests()
    return LifecycleService(
        session=db_session,
        lifecycle_root=lifecycle_root,
        counters=LifecycleCounters(),
        install_dispatcher=lambda *args, **kwargs: None,
    )


# ---- escalation_target column ---------------------------------------------


class TestEscalationTargetColumn:
    def test_alfred_form_defaults_null(
        self, service: LifecycleService, db_session: Session
    ):
        detail = service.create_request(NewRequestDraft(tool_name="csvkit"))
        assert detail.escalation_target is None
        row = db_session.query(Request).filter_by(filename=detail.filename).one()
        assert row.escalation_target is None

    def test_worker_form_persists_alfred(
        self, service: LifecycleService, db_session: Session
    ):
        detail = service.create_request(
            NewRequestDraft(
                tool_name="csvkit",
                agent_id="scout",
                escalation_target="alfred",
                gap="no CLI for column stats",
                workaround_used="pandas in REPL",
            )
        )
        assert detail.escalation_target == "alfred"
        row = db_session.query(Request).filter_by(filename=detail.filename).one()
        assert row.escalation_target == "alfred"

    def test_operator_target_persists(
        self, service: LifecycleService, db_session: Session
    ):
        """Alfred's onward escalation to operator. Stage 1.5 forward
        use; supported by the schema today.
        """
        detail = service.create_request(
            NewRequestDraft(
                tool_name="stripe-billing",
                agent_id="alfred",
                escalation_target="operator",
            )
        )
        assert detail.escalation_target == "operator"


# ---- Worker filename prefix -----------------------------------------------


class TestWorkerFilenamePrefix:
    @pytest.mark.parametrize(
        "worker", ["scout", "dispatch", "radar", "bridge"]
    )
    def test_worker_prefix_in_filename(
        self, worker, service: LifecycleService
    ):
        detail = service.create_request(
            NewRequestDraft(
                tool_name="csv-stats",
                agent_id=worker,
                escalation_target="alfred",
                gap="x",
                workaround_used="y",
            )
        )
        # Filename shape: YYYY-MM-DD-HHMM-worker-<name>-<slug>.md
        assert f"-worker-{worker}-csv-stats" in detail.filename
        assert detail.filename.endswith(".md")

    def test_alfred_form_keeps_bare_slug(self, service: LifecycleService):
        detail = service.create_request(NewRequestDraft(tool_name="csvkit"))
        # No `-worker-` infix.
        assert "-worker-" not in detail.filename
        assert detail.filename.endswith("-csvkit.md")

    def test_alfred_as_filer_no_prefix(self, service: LifecycleService):
        """`agent_id="alfred"` doesn't trigger the worker prefix —
        Alfred's filings keep the bare-slug filename per CLAUDE.md §6.
        """
        detail = service.create_request(
            NewRequestDraft(
                tool_name="stripe-billing",
                agent_id="alfred",
                escalation_target="operator",
            )
        )
        assert "-worker-" not in detail.filename


# ---- parsed_data["escalation"] propagation ---------------------------------


class TestParsedDataEscalation:
    def test_worker_form_populates_escalation_section(
        self, service: LifecycleService, db_session: Session
    ):
        detail = service.create_request(
            NewRequestDraft(
                tool_name="csvkit",
                agent_id="scout",
                escalation_target="alfred",
                gap="no installed CLI handles column-aware statistics",
                workaround_used="pandas inline in REPL, slower iteration",
            )
        )
        row = db_session.query(Request).filter_by(filename=detail.filename).one()
        escalation = row.parsed_data.get("escalation")
        assert escalation is not None
        assert escalation["worker"] == "scout"
        assert escalation["gap"] == "no installed CLI handles column-aware statistics"
        assert escalation["workaround_used"] == "pandas inline in REPL, slower iteration"

    def test_alfred_form_omits_escalation_section(
        self, service: LifecycleService, db_session: Session
    ):
        detail = service.create_request(
            NewRequestDraft(tool_name="csvkit", category="cli", confidence="high")
        )
        row = db_session.query(Request).filter_by(filename=detail.filename).one()
        assert "escalation" not in row.parsed_data


# ---- Markdown rendering ----------------------------------------------------


class TestMarkdownRendering:
    def test_worker_form_renders_escalation_section_header(self):
        draft = NewRequestDraft(
            tool_name="csvkit",
            agent_id="scout",
            escalation_target="alfred",
            gap="no CLI for column stats",
            workaround_used="pandas in REPL",
        )
        md = build_markdown(draft)
        assert "## Escalation" in md
        assert "**Worker:** scout" in md
        assert "**Gap:** no CLI for column stats" in md
        assert "**Workaround used:** pandas in REPL" in md

    def test_escalation_section_renders_between_request_and_recommendation(self):
        """Section order: Request → Escalation → Recommendation →
        Approval. Alfred reads the worker context before the
        recommendation rationale.
        """
        draft = NewRequestDraft(
            tool_name="csvkit",
            agent_id="scout",
            escalation_target="alfred",
            gap="x",
            workaround_used="y",
            why_this_tool="lightweight",
        )
        md = build_markdown(draft)
        req_idx = md.find("## Request")
        esc_idx = md.find("## Escalation")
        rec_idx = md.find("## Recommendation")
        assert req_idx < esc_idx < rec_idx
        assert req_idx != -1 and esc_idx != -1 and rec_idx != -1

    def test_h1_stays_tool_request_for_worker_form(self):
        """Per Decision N1 (Option β) — worker-form files use the
        unified `# Tool Request:` H1, NOT the prototype-era
        `# Worker Escalation:` H1. The Escalation section carries the
        worker context.
        """
        draft = NewRequestDraft(
            tool_name="csvkit",
            agent_id="scout",
            escalation_target="alfred",
            gap="x",
            workaround_used="y",
        )
        md = build_markdown(draft)
        assert "# Tool Request: csvkit" in md
        assert "# Worker Escalation:" not in md  # explicitly excluded


# ---- Backward-compat invariant (operator watch item) ----------------------


class TestAlfredFormBackwardCompat:
    """Operator watch item: Alfred-form drafts must produce
    byte-identical output to pre-item-5 build_markdown. Item 5's
    writer extension (the conditional Escalation section) must not
    accidentally drift Alfred-form rendering.
    """

    def test_minimal_alfred_form_byte_identical_to_expected(self):
        """The minimum draft (`tool_name="csvkit"`) renders to a
        known shape. Byte-equality pinned here so a future writer
        refactor that drifts Alfred-form output trips this test.
        """
        draft = NewRequestDraft(tool_name="csvkit")
        md = build_markdown(draft)

        expected = (
            "status: pending\n"
            "\n"
            "# Tool Request: csvkit\n"
            "\n"
            "## Request\n"
            "\n"
            "- **Task context:**\n"
            "- **Tool suggested:** csvkit\n"
            "- **Category:**\n"
            "- **Install method:**\n"
            "- **Discovered:** false\n"
            "\n"
            "## Recommendation\n"
            "\n"
            "- **Why this tool:**\n"
            "- **Alternatives considered:**\n"
            "- **Risk/cost:**\n"
            "- **Confidence:**\n"
            "\n"
            "## Approval\n"
            "\n"
            "- **Decision:**\n"
            "- **Conditions:**\n"
            "- **Date:**\n"
        )
        assert md == expected, (
            "Alfred-form rendering drifted from pre-item-5 shape. "
            "Investigate before merging."
        )

    def test_populated_alfred_form_no_escalation_header(self):
        draft = NewRequestDraft(
            tool_name="csvkit",
            category="cli",
            confidence="high",
            task_context="profiling a CSV",
            why_this_tool="lightweight",
        )
        md = build_markdown(draft)
        assert "## Escalation" not in md
        # All standard sections still present.
        assert "## Request" in md
        assert "## Recommendation" in md
        assert "## Approval" in md

    def test_alfred_form_round_trip_through_parser(self, tmp_path):
        """Alfred-form markdown → parser → parsed_data dict must
        match the pre-item-5 shape. The parser's parse_sections is
        section-name-agnostic, so an accidental Escalation section
        slip in Alfred-form would surface as parsed_data["escalation"]
        being populated.
        """
        draft = NewRequestDraft(
            tool_name="csvkit",
            category="cli",
            confidence="high",
        )
        path = tmp_path / "2026-05-14-1234-csvkit.md"
        path.write_text(build_markdown(draft))
        parsed = parse_request_file(path, "pending")
        assert "escalation" not in parsed.sections


# ---- Worker-form round-trip -----------------------------------------------


class TestWorkerFormRoundTrip:
    def test_full_roundtrip_through_parser(
        self, service: LifecycleService, db_session: Session
    ):
        """File written by the service is re-parsed by the cron path
        without losing the escalation section's content. This is the
        operational invariant — the cron must be able to round-trip
        worker-form files.
        """
        detail = service.create_request(
            NewRequestDraft(
                tool_name="csvkit",
                agent_id="scout",
                escalation_target="alfred",
                gap="no installed CLI handles column-aware statistics",
                workaround_used="pandas inline in REPL",
                task_context="profiling a subscriber CSV",
            )
        )
        # Re-parse from disk (not from DB) — that's what the cron does.
        from pathlib import Path
        path = Path(detail.folder) / detail.filename
        # detail.folder is "pending"; resolve under the lifecycle_root.
        full_path = service.lifecycle_root / detail.folder / detail.filename
        reparsed = parse_request_file(full_path, "pending")
        esc = reparsed.sections.get("escalation")
        assert esc is not None
        assert esc["worker"] == "scout"
        assert esc["gap"] == "no installed CLI handles column-aware statistics"
        assert esc["workaround_used"] == "pandas inline in REPL"

    def test_category_agnostic_skill_roundtrip(
        self, service: LifecycleService, db_session: Session
    ):
        """Items-5+6 scope clarification operator watch item:
        skill-request worker form must round-trip end-to-end (CLI
        invocation simulated here by direct service call → DB row →
        markdown → parse). No MCP-shape assumptions anywhere.
        """
        detail = service.create_request(
            NewRequestDraft(
                tool_name="claude-code-review-skill",
                category="skill",
                agent_id="scout",
                escalation_target="alfred",
                task_context="reviewing a PR for compliance with our brand voice",
                gap="no installed skill captures our brand-voice review patterns",
                workaround_used="did the review manually from memory",
                confidence="high",
            )
        )

        # DB row contains category="skill" + escalation_target="alfred".
        row = db_session.query(Request).filter_by(filename=detail.filename).one()
        assert row.category == "skill"
        assert row.escalation_target == "alfred"

        # Markdown has the right shape + no implicit MCP framing.
        full_path = service.lifecycle_root / detail.folder / detail.filename
        md = full_path.read_text(encoding="utf-8")
        assert "# Tool Request: claude-code-review-skill" in md
        assert "**Category:** skill" in md
        assert "## Escalation" in md
        assert "**Worker:** scout" in md
        assert "MCP" not in md  # category-agnostic; no leaked framing
        assert "mcp.servers" not in md

        # Parser round-trips the skill request cleanly.
        reparsed = parse_request_file(full_path, "pending")
        assert reparsed.category == "skill"
        assert reparsed.tool_name == "claude-code-review-skill"
        assert reparsed.sections["escalation"]["worker"] == "scout"
