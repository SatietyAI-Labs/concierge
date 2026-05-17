"""Tests for core/ingest/manifest.py — TOOL-MANIFEST.md → SQLite ingest.

Test surface organization
-------------------------

Five class groups + one capstone group, total 53 tests, each mapped to
a distinct parser path / equivalence rule / DB invariant:

1. TestParseCompoundStatusLine (5)
   - Parser-unit tests on parse_compound_status_line. One per
     distinct compound-line shape seen in the real manifest, plus
     the unknown-key drop path.

2. TestParseAlfredH3 (4)
   - One test per distinct H3-block parse path the Alfred section
     exercises: full-fields, Only-available-to, Tools-prefixed alias,
     missing-tool-count parenthetical.

3. TestParseBuildableH3 (3)
   - NOT YET BUILT, PARTIALLY BUILT, unknown-status fallback. Each
     tests a distinct status→lifecycle_state mapping path.

4. TestParseMcporter (2)
   - The H2-as-entry case; tool_type=cli; agent_owner stays NULL
     under "Available to:" (which is informational, not
     "Only available to:").

5. TestParseWorkerSection (4)
   - Cross-reference resolution; worker-only WARN+skip; no tool
     rows emitted from worker section; per-agent dispatch.

6. TestIngestEndToEnd (4)
   - Run ingest against the sanitized fixture; row count; lifecycle
     mapping; buildable handling.

7. TestIdempotency (3)
   - Re-run produces same row count; descriptive refresh; operator
     lifecycle preservation.

8. TestRoundTrip — Category I (10)
   - One test per Category-I incidental normalization rule
     (whitespace strip, internal collapse, backtick strip, lowercase
     agent_owner, lowercase auth, description synonymy, bullet
     order invariant, compound status segment order invariant,
     buildable tool_type stays NULL, whitespace in compound status).

9. TestRoundTrip — Category II (11)
   - One test per Category-II field (name, slug, tool_type,
     description, lifecycle_state, is_active, is_in_manifest,
     agent_owner, best_for, limitation, prefix, transport, auth).
     The slug case is consolidated into the name test (slug is
     derived); that brings the count to 11.

10. TestRoundTrip — Category III (5)
    - One test per Category-III passthrough/out-of-scope rule:
      H2 sections, informational bullets, worker-only refs,
      compound-status unknown keys, succeeded_by never set.

11. TestCapstoneRoundTrip (2)
    - test_full_fixture_parse_emit_reparse_equivalent — the big
      round-trip on the synthetic fixture.
    - test_actual_live_manifest_round_trips — skipped if the
      _legacy symlink isn't present (Concierge public-repo
      requirement).

12. TestFixtureSanitization (1)
    - Programmatic check that the fixture file carries no live API
      key prefixes, real domain names, or operator filesystem
      paths. Phase B operator review explicit requirement.

5 + 4 + 3 + 2 + 4 + 4 + 3 + 10 + 11 + 5 + 2 + 1 = 54 (one over the
plan-surface estimate of 53; the +1 is TestFixtureSanitization).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from core.db.base import Base
from core.db import models  # noqa: F401 — register on Base.metadata
from core.db.models import Tool
from core.ingest.manifest import (
    ManifestRow,
    dump_manifest,
    dump_tool_entry,
    equivalent,
    export_manifest,
    ingest_manifest,
    iter_manifest_rows,
    parse_compound_status_line,
    resolve_cross_references,
    tool_to_manifest_row,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "tool_manifest_excerpt.md"
_LEGACY_LIVE_MANIFEST = (
    Path("~/satietyai-upgrade/_legacy/agent-skills/shared/TOOL-MANIFEST.md")
    .expanduser()
)


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=True)
    s = factory()
    try:
        yield s
    finally:
        s.close()


def _make_row(**overrides) -> ManifestRow:
    """ManifestRow builder with sensible defaults; tests override only
    the fields under test."""
    defaults: dict[str, object] = dict(
        name="TestTool",
        slug="testtool",
        tool_type="mcp",
        description=None,
        lifecycle_state="loaded-on-boot",
        is_active=True,
        is_in_manifest=True,
        agent_owner=None,
        best_for=None,
        limitation=None,
        prefix=None,
        transport=None,
        auth=None,
    )
    defaults.update(overrides)
    return ManifestRow(**defaults)  # type: ignore[arg-type]


# =========================================================================
# 1. TestParseCompoundStatusLine
# =========================================================================


class TestParseCompoundStatusLine:
    """Parser-unit tests on the compound `**Status:**` value parser. The
    value can carry 1–3 pipe-delimited segments; the first is the status
    word(s), the rest are `Key: value` pseudo-bullets routed through the
    standard bullet dispatch."""

    def test_status_alone(self):
        """Single-segment: just the status word (buildable form)."""
        result = parse_compound_status_line("NOT YET BUILT")
        assert result == {"lifecycle_status_word": "NOT YET BUILT"}

    def test_status_plus_transport(self):
        """Two-segment: status + Transport (Firefox-style)."""
        result = parse_compound_status_line("ACTIVE | Transport: stdio (npx)")
        assert result == {
            "lifecycle_status_word": "ACTIVE",
            "transport": "stdio (npx)",
        }

    def test_status_plus_transport_and_auth(self):
        """Three-segment: status + Transport + Auth (MailerLite-style)."""
        result = parse_compound_status_line(
            "ACTIVE | Transport: stdio (node) | Auth: OAuth"
        )
        assert result == {
            "lifecycle_status_word": "ACTIVE",
            "transport": "stdio (node)",
            "auth": "OAuth",
        }

    def test_status_plus_informational_keys_dropped(self):
        """Port:, Key:, Binary:, Version: segments are informational and
        dropped silently (no WARN, since they're in the recognized
        informational set)."""
        result = parse_compound_status_line(
            "ACTIVE | Transport: stdio | Port: 9999 | Key: secret"
        )
        assert result == {
            "lifecycle_status_word": "ACTIVE",
            "transport": "stdio",
        }

    def test_status_plus_unknown_key_logs_warn_and_drops(self, caplog):
        """An unrecognized key in a compound Status segment is WARN-logged
        and dropped — surfacing manifest drift without halting ingest."""
        import logging
        with caplog.at_level(logging.WARNING, logger="concierge.ingest.manifest"):
            result = parse_compound_status_line(
                "ACTIVE | Transport: stdio | NewKey: foo"
            )
        assert result == {
            "lifecycle_status_word": "ACTIVE",
            "transport": "stdio",
        }
        assert any(
            "unknown_status_segment_key" in r.message for r in caplog.records
        )


# =========================================================================
# 2. TestParseAlfredH3
# =========================================================================


class TestParseAlfredH3:
    """One test per distinct H3-block parse path under
    `## ACTIVE CAPABILITIES — ALFRED`. Each exercises a code path the
    others don't (full fields, agent restriction, Tools-prefixed
    alias, optional tool-count parenthetical)."""

    def _parse_one(self, source: str) -> ManifestRow:
        rows, _, _ = iter_manifest_rows(source)
        assert len(rows) == 1, f"expected 1 row, got {len(rows)}"
        return rows[0]

    def test_alfred_h3_full_fields(self):
        """A fleet-wide MCP with every bullet populated — no Only-available-to.
        Exercises the default agent_owner=NULL path."""
        source = (
            "## ACTIVE CAPABILITIES — ALFRED\n\n"
            "### MCP Server: WidgetTool (6 tools)\n"
            "- **Status:** ACTIVE | Transport: stdio (npx)\n"
            "- **What it does:** Synthetic widget capability.\n"
            "- **Best for:** Full-fields parse path.\n"
            "- **Limitation:** Test fixture only.\n"
            "- **Prefix:** `widget_*`\n"
        )
        row = self._parse_one(source)
        assert row.name == "WidgetTool"
        assert row.tool_type == "mcp"
        assert row.lifecycle_state == "loaded-on-boot"
        assert row.is_active is True
        assert row.agent_owner is None
        assert row.transport == "stdio (npx)"
        assert row.description == "Synthetic widget capability."
        assert row.best_for == "Full-fields parse path."
        assert row.limitation == "Test fixture only."
        assert row.prefix == "widget_*"  # backticks stripped at parse

    def test_alfred_h3_only_available_to_extracts_agent_owner(self):
        """`Only available to: Alfred (...)` → agent_owner='alfred'.
        Tests the first-word extraction (the parenthetical comment is
        ignored)."""
        source = (
            "## ACTIVE CAPABILITIES — ALFRED\n\n"
            "### MCP Server: SecureWidget (4 tools)\n"
            "- **Status:** ACTIVE | Transport: stdio\n"
            "- **Only available to:** Alfred (workers use the other one)\n"
        )
        row = self._parse_one(source)
        assert row.agent_owner == "alfred"

    def test_alfred_h3_tools_prefixed_alias_maps_to_prefix(self):
        """`**Tools prefixed:** authed_*` is an alias for `**Prefix:**`
        used by the real manifest's MailerLite entry. Both keys must
        route to the same field."""
        source = (
            "## ACTIVE CAPABILITIES — ALFRED\n\n"
            "### MCP Server: AuthedService (10 tools)\n"
            "- **Status:** ACTIVE | Transport: stdio | Auth: API key (Synthetic)\n"
            "- **Tools prefixed:** `authed_*`\n"
        )
        row = self._parse_one(source)
        assert row.prefix == "authed_*"
        assert row.auth == "api key (synthetic)"  # lowercased

    def test_alfred_h3_missing_tool_count_parenthetical_still_parses(self):
        """`### MCP Server: Foo` (no `(N tools)` parenthetical) parses
        the same as `### MCP Server: Foo (24 tools)`. The exporter
        omits the parenthetical (informational); the parser tolerates
        both shapes for round-trip invertibility."""
        source = (
            "## ACTIVE CAPABILITIES — ALFRED\n\n"
            "### MCP Server: NoCount\n"
            "- **Status:** ACTIVE | Transport: stdio\n"
        )
        row = self._parse_one(source)
        assert row.name == "NoCount"
        assert row.tool_type == "mcp"
        assert row.transport == "stdio"


# =========================================================================
# 3. TestParseBuildableH3
# =========================================================================


class TestParseBuildableH3:
    """Buildable section H3 blocks: status maps to lifecycle_state via
    a distinct path (NOT YET BUILT / PARTIALLY BUILT → pending-decision;
    unknown → discovered + WARN). tool_type stays NULL per Decision 4a."""

    def _parse_one(self, source: str) -> ManifestRow:
        rows, _, _ = iter_manifest_rows(source)
        assert len(rows) == 1
        return rows[0]

    def test_buildable_not_yet_built_maps_to_pending_decision(self):
        source = (
            "## BUILDABLE (Custom Capabilities Needed)\n\n"
            "### Synthetic Build A\n"
            "- **Status:** NOT YET BUILT\n"
            "- **What it would do:** Synthetic future capability.\n"
        )
        row = self._parse_one(source)
        assert row.lifecycle_state == "pending-decision"
        assert row.is_active is False
        assert row.tool_type is None
        assert row.description == "Synthetic future capability."

    def test_buildable_partially_built_maps_to_pending_decision(self):
        """PARTIALLY BUILT is a distinct status string from NOT YET BUILT
        but maps to the same lifecycle_state — tested independently to
        confirm the dual-source mapping isn't a typo."""
        source = (
            "## BUILDABLE (Custom Capabilities Needed)\n\n"
            "### Synthetic Build B\n"
            "- **Status:** PARTIALLY BUILT\n"
        )
        row = self._parse_one(source)
        assert row.lifecycle_state == "pending-decision"
        assert row.is_active is False

    def test_buildable_unknown_status_falls_back_to_discovered_logs_warn(
        self, caplog
    ):
        """An unrecognized status string falls back to lifecycle_state=
        discovered and logs WARN. Surfaces manifest drift without
        halting ingest."""
        import logging
        source = (
            "## BUILDABLE (Custom Capabilities Needed)\n\n"
            "### Synthetic Build Unknown\n"
            "- **Status:** SOMETHING-UNKNOWN\n"
        )
        with caplog.at_level(logging.WARNING, logger="concierge.ingest.manifest"):
            row = self._parse_one(source)
        assert row.lifecycle_state == "discovered"
        assert any("unknown_status" in r.message for r in caplog.records)


# =========================================================================
# 4. TestParseMcporter
# =========================================================================


class TestParseMcporter:
    """The special H2-as-entry path for mcporter (paragraph-form bullets,
    not list-form). tool_type=cli; description stays NULL (mcporter's
    source uses prose paragraphs, not a `What it does` bullet)."""

    def test_mcporter_h2_entry_parses_as_cli(self):
        source = (
            "## AD-HOC MCP ACCESS (test-porter)\n\n"
            "**Status:** ACTIVE | Binary: `/tmp/test-porter` | Version: 0.0.0\n\n"
            "test-porter is a synthetic ad-hoc MCP launcher.\n\n"
            "**Available to:** All agents\n"
        )
        rows, _, _ = iter_manifest_rows(source)
        assert len(rows) == 1
        row = rows[0]
        assert row.name == "test-porter"
        assert row.tool_type == "cli"
        assert row.lifecycle_state == "loaded-on-boot"
        assert row.description is None  # prose-paragraph, not parsed

    def test_mcporter_available_to_no_op_on_agent_owner(self):
        """`Available to:` (informational) ≠ `Only available to:`
        (agent restriction). The parser must not populate agent_owner
        from `Available to:` because that bullet's semantic is
        fleet-wide-by-default, which is the NULL we already have."""
        source = (
            "## AD-HOC MCP ACCESS (test-porter)\n\n"
            "**Status:** ACTIVE\n\n"
            "**Available to:** All agents\n"
        )
        rows, _, _ = iter_manifest_rows(source)
        assert len(rows) == 1
        assert rows[0].agent_owner is None


# =========================================================================
# 5. TestParseWorkerSection
# =========================================================================


class TestParseWorkerSection:
    """Worker section produces cross-references, NOT tool rows. Each test
    exercises a distinct worker-section path."""

    def test_worker_section_resolves_cross_references_to_existing_tools(self):
        """If a worker references a tool whose Alfred H3 exists, the
        cross-reference resolves (counted in stats)."""
        source = (
            "## ACTIVE CAPABILITIES — ALFRED\n\n"
            "### MCP Server: WidgetTool (6 tools)\n"
            "- **Status:** ACTIVE | Transport: stdio\n\n"
            "## ACTIVE CAPABILITIES — WORKER AGENTS\n\n"
            "### TestWorker (Content) — 6 tools\n"
            "- WidgetTool (6)\n"
        )
        rows, xrefs, stats = iter_manifest_rows(source)
        resolve_cross_references(rows, xrefs, stats)
        assert stats.cross_references_resolved == 1
        assert stats.cross_references_skipped == 0

    def test_worker_only_reference_logs_warn_does_not_create_row(self, caplog):
        """A worker references a tool with NO Alfred H3 → WARN-log, skip.
        Per Decision 4a: do NOT auto-create a half-NULL row."""
        import logging
        source = (
            "## ACTIVE CAPABILITIES — WORKER AGENTS\n\n"
            "### TestWorker (Content) — 5 tools\n"
            "- UndocumentedTool (5)\n"
        )
        with caplog.at_level(logging.WARNING, logger="concierge.ingest.manifest"):
            rows, xrefs, stats = iter_manifest_rows(source)
            resolve_cross_references(rows, xrefs, stats)
        assert stats.cross_references_skipped == 1
        assert stats.cross_references_resolved == 0
        # No new row created for UndocumentedTool.
        assert all(r.name != "UndocumentedTool" for r in rows)
        assert any("worker_only_reference" in r.message for r in caplog.records)

    def test_worker_section_does_not_emit_tool_rows(self):
        """The worker section is parsed for cross-references only — it
        never emits a ManifestRow for the worker itself, regardless of
        what's inside it."""
        source = (
            "## ACTIVE CAPABILITIES — WORKER AGENTS\n\n"
            "### TestWorker (Content) — 6 tools\n"
            "- WidgetTool (6)\n"
        )
        rows, _, _ = iter_manifest_rows(source)
        assert rows == []

    def test_worker_section_dispatches_per_agent(self):
        """Multiple worker H3s under the same H2 each yield separate
        cross-reference entries."""
        source = (
            "## ACTIVE CAPABILITIES — ALFRED\n\n"
            "### MCP Server: WidgetTool (6 tools)\n"
            "- **Status:** ACTIVE | Transport: stdio\n\n"
            "## ACTIVE CAPABILITIES — WORKER AGENTS\n\n"
            "### WorkerA (Content) — 6 tools\n"
            "- WidgetTool (6)\n"
            "### WorkerB (Engagement) — 6 tools\n"
            "- WidgetTool (6)\n"
        )
        rows, xrefs, _ = iter_manifest_rows(source)
        # Two distinct worker entries; each carries one tool reference.
        agents = {agent for agent, _ in xrefs}
        assert agents == {"workera", "workerb"}


# =========================================================================
# 6. TestIngestEndToEnd
# =========================================================================


class TestIngestEndToEnd:
    """Run the ingest against the sanitized fixture and assert DB-level
    invariants. Each test exercises a distinct outcome."""

    def test_ingest_fixture_creates_expected_rows(self, session: Session):
        stats = ingest_manifest(FIXTURE_PATH, session)
        # 5 Alfred MCPs + 1 mcporter + 3 buildables = 9 entries from fixture
        assert stats.tools_created == 9
        assert stats.tools_updated == 0
        rows = session.query(Tool).all()
        slugs = {r.slug for r in rows}
        assert "widgettool" in slugs
        assert "test-porter" in slugs
        assert "synthetic-build-a" in slugs

    def test_ingest_returns_correct_stats(self, session: Session):
        stats = ingest_manifest(FIXTURE_PATH, session)
        # Tool-bearing sections: ALFRED + WORKER + AD-HOC + BUILDABLE = 4
        assert stats.sections_parsed == 4
        # Passthrough H2s in fixture: How to Use, FLEET OVERVIEW, DISCORD
        # VOICE PIPELINE, SHARED INFRASTRUCTURE, API KEYS, REQUESTING = 6.
        # The fixture's `# Tool Manifest Fixture` banner is H1 (not H2)
        # and is not counted by the section dispatcher.
        assert stats.sections_skipped == 6

    def test_ingest_marks_buildables_pending_decision(self, session: Session):
        ingest_manifest(FIXTURE_PATH, session)
        buildables = (
            session.query(Tool)
            .filter(Tool.lifecycle_state == "pending-decision")
            .all()
        )
        # Both NOT YET BUILT entries map to pending-decision; the
        # SOMETHING-UNKNOWN one falls back to discovered.
        assert len(buildables) == 2
        names = {b.name for b in buildables}
        assert "Synthetic Build A" in names
        assert "Synthetic Build B" in names

    def test_ingest_lifecycle_state_loaded_on_boot_for_active_mcps(
        self, session: Session
    ):
        ingest_manifest(FIXTURE_PATH, session)
        active = (
            session.query(Tool)
            .filter(Tool.lifecycle_state == "loaded-on-boot")
            .all()
        )
        # 5 Alfred MCPs + 1 mcporter = 6 active entries
        assert len(active) == 6
        # (The retired `is_active` cross-check was dropped here — D112;
        # `lifecycle_state` is the canonical authority the filter uses.)


# =========================================================================
# 7. TestIdempotency
# =========================================================================


class TestIdempotency:
    """Re-running ingest against the same source must not duplicate rows
    or clobber operator-managed lifecycle fields."""

    def test_re_ingest_produces_same_row_count(self, session: Session):
        s1 = ingest_manifest(FIXTURE_PATH, session)
        s2 = ingest_manifest(FIXTURE_PATH, session)
        assert s1.tools_created == 9
        # Second run finds every row; updates them (no new creates).
        assert s2.tools_created == 0
        assert s2.tools_updated == 9
        # Total Tool count unchanged.
        assert session.query(Tool).count() == 9

    def test_re_ingest_refreshes_descriptive_fields(self, session: Session):
        """If a descriptive field is changed in source (simulated via
        direct DB edit), re-ingest refreshes it back to source value."""
        ingest_manifest(FIXTURE_PATH, session)
        widget = session.query(Tool).filter_by(slug="widgettool").one()
        widget.description = "OPERATOR-EDITED PLACEHOLDER"
        session.commit()
        ingest_manifest(FIXTURE_PATH, session)
        session.refresh(widget)
        assert widget.description == (
            "Synthetic widget-management capability for tests."
        )

    def test_re_ingest_preserves_operator_set_lifecycle_state(
        self, session: Session
    ):
        """Operator-managed lifecycle_state (anything other than the
        parser default for the source) is preserved on re-ingest. The
        parser only updates lifecycle_state when DB still has the
        default-from-ingest value AND the source matches."""
        ingest_manifest(FIXTURE_PATH, session)
        widget = session.query(Tool).filter_by(slug="widgettool").one()
        # Operator demotes the row to discovered (e.g., taking it offline).
        # Use raw SQL to bypass the transition listener — see
        # tests/test_tool_transitions.py::TestRawSqlBypass for precedent.
        from sqlalchemy import text
        session.execute(
            text("UPDATE tools SET lifecycle_state = 'discovered' "
                 "WHERE slug = 'widgettool'")
        )
        session.commit()
        session.refresh(widget)
        assert widget.lifecycle_state == "discovered"
        # Now re-ingest. The row stays at the operator-set value because
        # source says loaded-on-boot but the DB-side discovered is treated
        # as the refresh-allowed default — so the parser re-applies the
        # source state. This is the documented "discovered → re-apply"
        # branch in ingest_manifest. Operator-set NON-discovered states
        # are the truly protected ones.
        ingest_manifest(FIXTURE_PATH, session)
        session.refresh(widget)
        assert widget.lifecycle_state == "loaded-on-boot"
        # Now retry with an operator-set NON-discovered state.
        session.execute(
            text("UPDATE tools SET lifecycle_state = 'retired' "
                 "WHERE slug = 'widgettool'")
        )
        session.commit()
        ingest_manifest(FIXTURE_PATH, session)
        session.refresh(widget)
        # `retired` is preserved across re-ingest.
        assert widget.lifecycle_state == "retired"


# =========================================================================
# 8. TestRoundTrip — Category I (incidental normalizations)
# =========================================================================


class TestRoundTripCategoryI:
    """For each Category-I normalization rule, build a ManifestRow with
    raw-ish input, dump→reparse, and assert the round-trip equivalence.
    Each test pins one normalization path."""

    def _round_trip(self, row: ManifestRow) -> ManifestRow:
        """Dump → reparse the single row, return the parsed back."""
        dumped = dump_tool_entry(row)
        rows, _, _ = iter_manifest_rows(dumped)
        assert len(rows) == 1
        return rows[0]

    def test_normalize_strips_trailing_whitespace_on_name(self):
        """I.1 — name with trailing whitespace round-trips equivalent."""
        row = _make_row(name="WidgetTool")
        # Manually inject whitespace to simulate source noise.
        row.name = "WidgetTool   "
        result = self._round_trip(row)
        assert equivalent(row, result)
        assert result.name == "WidgetTool"

    def test_normalize_collapses_internal_whitespace_in_description(self):
        """I.2 — internal whitespace runs collapsed to single space."""
        row = _make_row(
            description="multi   space   description"
        )
        result = self._round_trip(row)
        assert equivalent(row, result)

    def test_normalize_strips_backticks_on_prefix(self):
        """I.3 — prefix stored without backticks; exporter re-wraps; parser
        re-strips on re-parse."""
        row = _make_row(prefix="widget_*")
        dumped = dump_tool_entry(row)
        # Exporter emits ` `widget_*` ` (backticked).
        assert "`widget_*`" in dumped
        result = self._round_trip(row)
        assert result.prefix == "widget_*"  # parser re-strips
        assert equivalent(row, result)

    def test_normalize_lowercases_agent_owner(self):
        """I.4 — agent_owner stored lowercase. Exporter capitalizes; parser
        re-lowercases."""
        row = _make_row(agent_owner="alfred")
        dumped = dump_tool_entry(row)
        # Exporter emits "Alfred" for readability.
        assert "Alfred" in dumped
        result = self._round_trip(row)
        assert result.agent_owner == "alfred"
        assert equivalent(row, result)

    def test_normalize_lowercases_auth(self):
        """I.5 — auth stored lowercase, round-trip preserves the lowercased
        form regardless of source casing."""
        row = _make_row(auth="oauth")
        result = self._round_trip(row)
        assert result.auth == "oauth"
        assert equivalent(row, result)

    def test_description_synonymy_buildable_uses_what_it_would_do(self):
        """I.6 — `What it would do` (buildable) and `What it does` (active)
        both populate description. Exporter picks by lifecycle_state."""
        row = _make_row(
            tool_type=None,
            lifecycle_state="pending-decision",
            is_active=False,
            description="Future capability.",
        )
        dumped = dump_tool_entry(row)
        assert "What it would do" in dumped
        result = self._round_trip(row)
        assert result.description == "Future capability."
        assert equivalent(row, result)

    def test_bullet_emission_canonical_order_is_parse_invariant(self):
        """I.7 — the parser is insensitive to bullet ordering. Build a
        manifest excerpt with bullets in a NON-canonical order; assert
        parsed result matches a canonical-order round-trip."""
        non_canonical = (
            "## ACTIVE CAPABILITIES — ALFRED\n\n"
            "### MCP Server: WidgetTool\n"
            "- **Prefix:** `widget_*`\n"
            "- **Limitation:** Test only.\n"
            "- **What it does:** Synthetic.\n"
            "- **Status:** ACTIVE | Transport: stdio\n"
            "- **Best for:** Order test.\n"
        )
        rows_a, _, _ = iter_manifest_rows(non_canonical)
        # Round-trip the parsed row.
        round_tripped = self._round_trip(rows_a[0])
        assert equivalent(rows_a[0], round_tripped)

    def test_compound_status_segment_order_is_parse_invariant(self):
        """I.8 — segments within a `**Status:**` value can appear in any
        order. The parser splits on `|` and routes by key."""
        source_a = (
            "## ACTIVE CAPABILITIES — ALFRED\n\n"
            "### MCP Server: WidgetTool\n"
            "- **Status:** ACTIVE | Transport: stdio | Auth: OAuth\n"
        )
        source_b = (
            "## ACTIVE CAPABILITIES — ALFRED\n\n"
            "### MCP Server: WidgetTool\n"
            "- **Status:** ACTIVE | Auth: OAuth | Transport: stdio\n"
        )
        rows_a, _, _ = iter_manifest_rows(source_a)
        rows_b, _, _ = iter_manifest_rows(source_b)
        assert equivalent(rows_a[0], rows_b[0])

    def test_buildable_tool_type_stays_null_through_round_trip(self):
        """I.9 — buildable's tool_type=NULL invariant: dump → reparse
        keeps it NULL, not coerced to mcp/cli."""
        row = _make_row(
            tool_type=None,
            lifecycle_state="pending-decision",
            is_active=False,
        )
        result = self._round_trip(row)
        assert result.tool_type is None
        assert equivalent(row, result)

    def test_minor_whitespace_in_compound_status_normalized(self):
        """I.10 — extra whitespace around the `|` separator doesn't change
        parse output."""
        source_a = (
            "## ACTIVE CAPABILITIES — ALFRED\n\n"
            "### MCP Server: Foo\n"
            "- **Status:** ACTIVE | Transport: stdio\n"
        )
        source_b = (
            "## ACTIVE CAPABILITIES — ALFRED\n\n"
            "### MCP Server: Foo\n"
            "- **Status:** ACTIVE  |  Transport: stdio  \n"
        )
        rows_a, _, _ = iter_manifest_rows(source_a)
        rows_b, _, _ = iter_manifest_rows(source_b)
        assert equivalent(rows_a[0], rows_b[0])


# =========================================================================
# 9. TestRoundTrip — Category II (per-field byte-equal after normalize)
# =========================================================================


class TestRoundTripCategoryII:
    """One test per Category-II field. Each builds a row with a non-default
    value in exactly one field, round-trips, asserts the field survived
    intact."""

    def _round_trip(self, row: ManifestRow) -> ManifestRow:
        dumped = dump_tool_entry(row)
        rows, _, _ = iter_manifest_rows(dumped)
        assert len(rows) == 1
        return rows[0]

    def test_name_round_trips(self):
        row = _make_row(name="DistinctWidget")
        result = self._round_trip(row)
        assert result.name == "DistinctWidget"

    def test_tool_type_round_trips_mcp(self):
        row = _make_row(tool_type="mcp")
        result = self._round_trip(row)
        assert result.tool_type == "mcp"

    def test_description_round_trips(self):
        row = _make_row(description="A specific description string.")
        result = self._round_trip(row)
        assert result.description == "A specific description string."

    def test_lifecycle_state_loaded_on_boot_round_trips(self):
        row = _make_row(lifecycle_state="loaded-on-boot", is_active=True)
        result = self._round_trip(row)
        assert result.lifecycle_state == "loaded-on-boot"

    def test_lifecycle_state_pending_decision_round_trips(self):
        row = _make_row(
            tool_type=None,
            lifecycle_state="pending-decision",
            is_active=False,
        )
        result = self._round_trip(row)
        assert result.lifecycle_state == "pending-decision"

    def test_is_active_round_trips(self):
        """is_active is derived from lifecycle_state but tested as a
        separate field — if the derivation rule breaks, this catches it."""
        row = _make_row(lifecycle_state="loaded-on-boot", is_active=True)
        result = self._round_trip(row)
        assert result.is_active is True

    def test_is_in_manifest_round_trips(self):
        """The parser only emits rows seen IN the manifest, so
        is_in_manifest is invariantly True. Test it stays so on
        round-trip."""
        row = _make_row(is_in_manifest=True)
        result = self._round_trip(row)
        assert result.is_in_manifest is True

    def test_agent_owner_round_trips(self):
        row = _make_row(agent_owner="alfred")
        result = self._round_trip(row)
        assert result.agent_owner == "alfred"

    def test_best_for_round_trips(self):
        row = _make_row(best_for="A specific best-for prose.")
        result = self._round_trip(row)
        assert result.best_for == "A specific best-for prose."

    def test_limitation_round_trips(self):
        row = _make_row(limitation="A specific limitation prose.")
        result = self._round_trip(row)
        assert result.limitation == "A specific limitation prose."

    def test_prefix_round_trips(self):
        row = _make_row(prefix="distinct_*")
        result = self._round_trip(row)
        assert result.prefix == "distinct_*"

    def test_transport_round_trips(self):
        row = _make_row(transport="stdio (test-form)")
        result = self._round_trip(row)
        assert result.transport == "stdio (test-form)"

    def test_auth_round_trips(self):
        row = _make_row(auth="api key (synthetic)")
        result = self._round_trip(row)
        assert result.auth == "api key (synthetic)"


# =========================================================================
# 10. TestRoundTrip — Category III (passthrough / out-of-scope)
# =========================================================================


class TestRoundTripCategoryIII:
    """Out-of-scope content does NOT survive round-trip — and that's the
    point. These tests verify the parser/exporter correctly DROPS what
    should be dropped."""

    def test_passthrough_h2_sections_not_consumed(self):
        """H2 sections in the passthrough list (FLEET OVERVIEW, SHARED
        INFRASTRUCTURE, etc.) don't produce any ManifestRow."""
        source = (
            "## FLEET OVERVIEW\n\n"
            "| Agent | Port |\n|---|---|\n| Primary | 10000 |\n\n"
            "## SHARED INFRASTRUCTURE\n\n"
            "### Content Pipeline\n"
            "Some prose.\n"
        )
        rows, _, stats = iter_manifest_rows(source)
        assert rows == []
        assert stats.sections_skipped == 2

    def test_informational_bullets_dropped(self):
        """Bullets like Runs, Extension, Secret, Tools, Env var, Model
        are dropped at parse time — they don't appear in the
        ManifestRow's parsed fields."""
        source = (
            "## ACTIVE CAPABILITIES — ALFRED\n\n"
            "### MCP Server: WidgetTool\n"
            "- **Status:** ACTIVE | Transport: stdio\n"
            "- **What it does:** Synthetic.\n"
            "- **Runs:** A test process.\n"
            "- **Extension:** /tmp/fake\n"
            "- **Tools:** w_a, w_b, w_c\n"
            "- **Env var:** FAKE_VAR\n"
        )
        rows, _, _ = iter_manifest_rows(source)
        assert len(rows) == 1
        row = rows[0]
        # Description is the only prose captured.
        assert row.description == "Synthetic."
        # No field carries the dropped data.
        for field_value in (
            row.best_for, row.limitation, row.prefix, row.auth, row.agent_owner
        ):
            assert "test process" not in (field_value or "")
            assert "/tmp/fake" not in (field_value or "")

    def test_compound_status_unknown_keys_dropped(self):
        """Sub-segment keys like Port, Key, Binary, Version are
        informational and dropped from the parse output."""
        source = (
            "## ACTIVE CAPABILITIES — ALFRED\n\n"
            "### MCP Server: WidgetTool\n"
            "- **Status:** ACTIVE | Transport: stdio | Port: 9999 | Key: hidden\n"
        )
        rows, _, _ = iter_manifest_rows(source)
        # No field carries the Port or Key value.
        assert rows[0].transport == "stdio"
        # Round-trip does NOT re-emit them.
        dumped = dump_tool_entry(rows[0])
        assert "Port" not in dumped
        assert "Key:" not in dumped

    def test_worker_only_reference_skipped_not_in_rows(self):
        """Worker-only tool name (e.g., UndocumentedTool) with no Alfred
        H3 is logged WARN and NOT emitted as a row."""
        source = (
            "## ACTIVE CAPABILITIES — WORKER AGENTS\n\n"
            "### TestWorker (Content) — 5 tools\n"
            "- UndocumentedTool (5)\n"
        )
        rows, _, stats = iter_manifest_rows(source)
        assert rows == []

    def test_succeeded_by_never_set_by_parser(self, session: Session):
        """succeeded_by is the sole responsibility of the Stage-0
        reconciliation slice; the manifest parser never sets it. All
        ingested rows have succeeded_by=NULL even when lifecycle_state
        is something the reconciliation slice would later mark."""
        ingest_manifest(FIXTURE_PATH, session)
        for tool in session.query(Tool).all():
            assert tool.succeeded_by is None


# =========================================================================
# 11. TestCapstoneRoundTrip
# =========================================================================


class TestCapstoneRoundTrip:
    """The big round-trip: every row in a multi-section parse survives
    dump_manifest → re-parse via `equivalent()`."""

    def test_full_fixture_parse_emit_reparse_equivalent(self):
        text = FIXTURE_PATH.read_text(encoding="utf-8")
        rows_a, _, _ = iter_manifest_rows(text)
        assert len(rows_a) == 9  # 5 mcp + 1 cli (mcporter) + 3 buildables
        dumped = dump_manifest(rows_a)
        rows_b, _, _ = iter_manifest_rows(dumped)
        # Same number of rows.
        assert len(rows_b) == len(rows_a)
        # Each row equivalent. Match by slug since order may differ.
        by_slug_a = {r.slug: r for r in rows_a}
        by_slug_b = {r.slug: r for r in rows_b}
        assert set(by_slug_a.keys()) == set(by_slug_b.keys())
        for slug in by_slug_a:
            assert equivalent(by_slug_a[slug], by_slug_b[slug]), (
                f"round-trip failed for {slug!r}:\n"
                f"  before: {by_slug_a[slug]}\n"
                f"  after:  {by_slug_b[slug]}"
            )

    def test_count_invariant_no_row_dropped_for_arbitrary_bucket_mix(self):
        """Pin the no-row-dropped invariant for dump_manifest directly,
        independent of any fixture content. The catch-all bucketing rule
        ("anything not mcp/cli routes to BUILDABLE") was added during
        Phase B build after a SOMETHING-UNKNOWN buildable in the fixture
        surfaced the silent-drop class. The fixture catch was the
        INSTANCE; this test pins the CLASS.

        Build a constructed mix with one row in each bucket category —
        mcp + cli + tool_type=None+pending-decision + tool_type=None+
        discovered (the unknown-status fallback shape) — and assert
        round-trip preserves the row count. Without this guard a future
        refactor that re-narrows BUILDABLE (e.g., back to a strict
        `lifecycle_state=='pending-decision'` filter) would silently
        drop the fallback row again; this test fires immediately.

        Mirrors `TestParseWorkerSection::test_worker_section_does_not_emit_tool_rows` —
        an inverse-property guard pinning a design decision against
        future drift."""

        rows_in = [
            # Bucket 1: mcp → ALFRED section.
            _make_row(name="McpTool", slug="mcptool", tool_type="mcp"),
            # Bucket 2: cli → AD-HOC section.
            _make_row(
                name="cli-tool",
                slug="cli-tool",
                tool_type="cli",
                lifecycle_state="loaded-on-boot",
                is_active=True,
            ),
            # Bucket 3 (catch-all variant A): tool_type=None +
            # lifecycle_state=pending-decision → BUILDABLE section.
            _make_row(
                name="BuildableA",
                slug="buildablea",
                tool_type=None,
                lifecycle_state="pending-decision",
                is_active=False,
            ),
            # Bucket 4 (catch-all variant B): tool_type=None +
            # lifecycle_state=discovered (the unknown-status fallback
            # shape). Without the catch-all rule this row would be
            # silently dropped at dump time.
            _make_row(
                name="DiscoveredFallback",
                slug="discoveredfallback",
                tool_type=None,
                lifecycle_state="discovered",
                is_active=False,
            ),
        ]
        dumped = dump_manifest(rows_in)
        rows_out, _, _ = iter_manifest_rows(dumped)
        assert len(rows_out) == len(rows_in), (
            f"row count not preserved through dump_manifest → reparse:\n"
            f"  in  ({len(rows_in)}):  {[r.name for r in rows_in]}\n"
            f"  out ({len(rows_out)}): {[r.name for r in rows_out]}"
        )
        # Also pin slug-set preservation so a future bug that emits the
        # right COUNT but the wrong rows (e.g., one row duplicated and
        # another silently swapped) fails distinctly.
        in_slugs = {r.slug for r in rows_in}
        out_slugs = {r.slug for r in rows_out}
        assert in_slugs == out_slugs, (
            f"slug set not preserved through round-trip:\n"
            f"  in:  {sorted(in_slugs)}\n"
            f"  out: {sorted(out_slugs)}"
        )

    @pytest.mark.skipif(
        not _LEGACY_LIVE_MANIFEST.exists(),
        reason="_legacy live manifest not available (fresh clone of public repo)",
    )
    def test_actual_live_manifest_round_trips(self):
        """Live-manifest round-trip. Skipped on a fresh clone of the
        Concierge public repo (no `_legacy` symlink); active in the
        upgrade workspace where the symlink resolves to the real
        manifest at ~/.agent-skills/shared/TOOL-MANIFEST.md.

        This test is the reality-drift catch: the synthetic fixture
        exercises every parser path the author anticipated, but the
        live manifest is the ground truth for "the parser actually
        handles the format we ship against."
        """
        text = _LEGACY_LIVE_MANIFEST.read_text(encoding="utf-8")
        rows_a, _, _ = iter_manifest_rows(text)
        assert rows_a, "live manifest produced zero rows — parser regression"
        dumped = dump_manifest(rows_a)
        rows_b, _, _ = iter_manifest_rows(dumped)
        assert len(rows_b) == len(rows_a)
        by_slug_a = {r.slug: r for r in rows_a}
        by_slug_b = {r.slug: r for r in rows_b}
        assert set(by_slug_a.keys()) == set(by_slug_b.keys())
        for slug in by_slug_a:
            assert equivalent(by_slug_a[slug], by_slug_b[slug]), (
                f"live-manifest round-trip failed for {slug!r}"
            )


# =========================================================================
# 12. TestFixtureSanitization
# =========================================================================


class TestFixtureSanitization:
    """Programmatic sanitization check. Concierge is a public repo;
    the fixture must not leak operator-side credentials, real domains,
    or filesystem paths from the live manifest. This test is the
    operator-mandated automated verification of that property."""

    def test_fixture_contains_no_real_credentials(self):
        text = FIXTURE_PATH.read_text(encoding="utf-8")
        # Live API key prefixes that would never appear in a sanitized
        # fixture. The presence of any of these is a leak indicator.
        forbidden_patterns = [
            r"\bsk_live_[A-Za-z0-9]{16,}",          # Stripe live secret
            r"\bsk_test_[A-Za-z0-9]{16,}",          # Stripe test secret
            r"\bpk_live_[A-Za-z0-9]{16,}",          # Stripe live publishable
            r"\beyJ[A-Za-z0-9_-]{20,}",             # JWT prefix
            r"\b(satietyai|moltbot|openclaw)\.io\b",  # Real domains
            r"/home/satiety/",                      # Real operator path
            r"~/satietyai-",                        # Real workspace path
            r"\b18789\b|\b18800\b|\b18810\b|\b18820\b|\b18830\b",  # Real ports
            r"\bsatietyllc@",                       # Operator email
            r"7p1Ofvcwsv7UBPoFNcpI",                # ElevenLabs voice ID from manifest
            r"e1163942-45df-4c43-bd17-8a82bd5556df", # Browser-control secret from manifest
            r"180787422651483855",                  # MailerLite group ID from manifest
            r"181409024921568935",                  # MailerLite automation ID from manifest
        ]
        leaks = []
        for pattern in forbidden_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                leaks.append((pattern, matches))
        assert not leaks, (
            f"fixture contains sensitive patterns that must be removed:\n"
            + "\n".join(f"  {p}: {m}" for p, m in leaks)
        )


# =========================================================================
# 13. TestToolToManifestRow — DB row → ManifestRow reconstruction
# =========================================================================


class TestToolToManifestRow:
    """`tool_to_manifest_row` reconstructs a ManifestRow from a persisted
    Tool — the inverse of `ingest_manifest`'s row construction. The DB
    stores parser-canonical values verbatim, so reconstruction is a
    plain field copy."""

    def test_reconstructs_every_manifestrow_field(self, session: Session):
        """A fully-populated Tool reconstructs to a ManifestRow whose
        every field equals the source column."""
        tool = Tool(
            slug="firefox-devtools",
            name="Firefox DevTools",
            description="Browser automation MCP.",
            tool_type="mcp",
            is_in_manifest=True,
            lifecycle_state="loaded-on-boot",
            agent_owner="alfred",
            best_for="Web scraping and form automation.",
            limitation="Single-tab; no parallel sessions.",
            prefix="firefox_*",
            transport="stdio (npx)",
            auth="none",
        )
        session.add(tool)
        session.commit()

        row = tool_to_manifest_row(tool)
        assert row.name == "Firefox DevTools"
        assert row.slug == "firefox-devtools"
        assert row.tool_type == "mcp"
        assert row.description == "Browser automation MCP."
        assert row.lifecycle_state == "loaded-on-boot"
        # `is_active` is re-derived by tool_to_manifest_row from
        # `lifecycle_state` (the `Tool.is_active` column was retired —
        # D112); loaded-on-boot → True.
        assert row.is_active is True
        assert row.is_in_manifest is True
        assert row.agent_owner == "alfred"
        assert row.best_for == "Web scraping and form automation."
        assert row.limitation == "Single-tab; no parallel sessions."
        assert row.prefix == "firefox_*"
        assert row.transport == "stdio (npx)"
        assert row.auth == "none"

    def test_buildable_tool_type_none_reconstructs(self, session: Session):
        """A buildable row (tool_type=None) reconstructs with tool_type
        None — load-bearing for dump_manifest's BUILDABLE bucketing."""
        tool = Tool(
            slug="cron-scheduling",
            name="Cron Scheduling",
            tool_type=None,
            is_in_manifest=True,
            lifecycle_state="pending-decision",
        )
        session.add(tool)
        session.commit()
        row = tool_to_manifest_row(tool)
        assert row.tool_type is None
        assert row.lifecycle_state == "pending-decision"
        assert row.is_active is False

    def test_null_optional_columns_stay_none(self, session: Session):
        """Tool optional columns left NULL reconstruct as None on the
        ManifestRow — no spurious empty strings."""
        tool = Tool(
            slug="bare-tool",
            name="BareTool",
            tool_type="cli",
            is_in_manifest=True,
            lifecycle_state="loaded-on-boot",
        )
        session.add(tool)
        session.commit()
        row = tool_to_manifest_row(tool)
        for field_name in (
            "description", "agent_owner", "best_for", "limitation",
            "prefix", "transport", "auth",
        ):
            assert getattr(row, field_name) is None, field_name

    def test_succeeded_by_not_carried_onto_manifestrow(
        self, session: Session
    ):
        """succeeded_by is not a ManifestRow field — even a Tool with
        succeeded_by set reconstructs to a row with no such attribute.
        Pins D79: succeeded_by is outside the manifest round-trip
        entirely (the parser never sets it; the export never reads it)."""
        tool = Tool(
            slug="mailerlite",
            name="MailerLite",
            tool_type="mcp",
            is_in_manifest=True,
            lifecycle_state="retired",
            succeeded_by="ghl",
        )
        session.add(tool)
        session.commit()
        row = tool_to_manifest_row(tool)
        assert not hasattr(row, "succeeded_by")


# =========================================================================
# 14. TestExportManifest — SQLite catalog → markdown
# =========================================================================


class TestExportManifest:
    """`export_manifest(session)` renders is_in_manifest=True Tool rows
    to canonical manifest markdown via dump_manifest."""

    def test_empty_catalog_exports_empty(self, session: Session):
        """No Tool rows → dump_manifest([]) → a lone newline."""
        assert export_manifest(session) == "\n"

    def test_excludes_is_in_manifest_false_rows(self, session: Session):
        """A Tool with is_in_manifest=False is NOT exported — only
        manifest-sourced rows round-trip; catalog/skills-sourced and
        operator-added rows are excluded."""
        session.add(Tool(
            slug="catalog-only", name="CatalogOnly", tool_type="mcp",
            is_in_manifest=False,
            lifecycle_state="loaded-on-boot",
        ))
        session.add(Tool(
            slug="from-manifest", name="FromManifest", tool_type="mcp",
            is_in_manifest=True,
            lifecycle_state="loaded-on-boot",
        ))
        session.commit()
        out = export_manifest(session)
        assert "FromManifest" in out
        assert "CatalogOnly" not in out

    def test_exported_markdown_reparses_to_the_source_rows(
        self, session: Session
    ):
        """export_manifest output is parseable by iter_manifest_rows and
        yields exactly the exported rows. The slug is re-derived from
        the name on re-parse (it is not stored in the markdown), so the
        row's name and slug are kept consistent here — as every
        ingest_manifest-written row already is (slug = slugify(name))."""
        session.add(Tool(
            slug="reparse-me", name="Reparse Me", tool_type="mcp",
            is_in_manifest=True,
            lifecycle_state="loaded-on-boot",
        ))
        session.commit()
        rows, _, _ = iter_manifest_rows(export_manifest(session))
        assert [r.slug for r in rows] == ["reparse-me"]
        assert [r.name for r in rows] == ["Reparse Me"]


# =========================================================================
# 15. TestDbRoundTrip — the DB-grounded round-trip (Gate 2 fidelity claim)
# =========================================================================


class TestDbRoundTrip:
    """The DB-grounded round-trip: ingest_manifest → DB → export_manifest
    → re-parse must yield rows equivalent to the originals.

    Distinct from TestCapstoneRoundTrip's parse/emit round-trip — this
    one exercises the SQLite write+read layer, which is the actual
    fidelity claim Stage 1B Gate 2 exists to verify (the master plan
    risk register's "catalog ingest loses metadata from TOOL-MANIFEST.md
    → round-trip diff validation at Gate 2"). A text→parse→emit→reparse
    round-trip never touches the DB and so cannot catch a metadata-loss
    bug in the persistence layer."""

    def test_fixture_db_round_trip_equivalent(self, session: Session):
        """Every fixture row survives ingest → DB → export → re-parse
        under equivalent(). The DB analogue of
        test_full_fixture_parse_emit_reparse_equivalent."""
        rows_a, _, _ = iter_manifest_rows(
            FIXTURE_PATH.read_text(encoding="utf-8")
        )
        ingest_manifest(FIXTURE_PATH, session)
        rows_b, _, _ = iter_manifest_rows(export_manifest(session))
        by_slug_a = {r.slug: r for r in rows_a}
        by_slug_b = {r.slug: r for r in rows_b}
        assert set(by_slug_a) == set(by_slug_b)
        for slug in by_slug_a:
            assert equivalent(by_slug_a[slug], by_slug_b[slug]), (
                f"DB round-trip failed for {slug!r}:\n"
                f"  before: {by_slug_a[slug]}\n"
                f"  after:  {by_slug_b[slug]}"
            )

    def test_db_round_trip_count_and_slug_set_preserved(
        self, session: Session
    ):
        """No row dropped or added through the DB round-trip; slug set
        identical. Pins the no-row-lost invariant against the
        persistence layer specifically."""
        rows_a, _, _ = iter_manifest_rows(
            FIXTURE_PATH.read_text(encoding="utf-8")
        )
        ingest_manifest(FIXTURE_PATH, session)
        rows_b, _, _ = iter_manifest_rows(export_manifest(session))
        assert len(rows_b) == len(rows_a) == 9
        assert {r.slug for r in rows_b} == {r.slug for r in rows_a}

    def test_db_round_trip_preserves_catalog_metadata(
        self, session: Session
    ):
        """The catalog-metadata fields survive the SQLite layer
        specifically — the metadata-loss risk Gate 2's round-trip diff
        exists to catch. AuthedService carries the richest metadata in
        the fixture: description, best_for, agent_owner, prefix,
        transport, auth."""
        ingest_manifest(FIXTURE_PATH, session)
        tool = session.query(Tool).filter_by(name="AuthedService").one()
        # Ingest populated the metadata columns from the manifest.
        assert tool.agent_owner == "alfred"
        assert tool.auth == "api key (synthetic)"
        assert tool.transport == "stdio (uvx)"
        assert tool.prefix == "authed_*"
        assert tool.best_for is not None
        assert tool.description is not None
        # Export → re-parse preserves every one of them.
        rows_b, _, _ = iter_manifest_rows(export_manifest(session))
        reparsed = {r.slug: r for r in rows_b}[tool.slug]
        assert reparsed.agent_owner == tool.agent_owner
        assert reparsed.auth == tool.auth
        assert reparsed.transport == tool.transport
        assert reparsed.prefix == tool.prefix
        assert reparsed.best_for == tool.best_for
        assert reparsed.description == tool.description
