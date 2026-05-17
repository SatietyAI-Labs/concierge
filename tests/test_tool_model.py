"""Tests for the seven nullable catalog-metadata columns added to Tool
in Stage 1A item 4 (alembic revision `fa46ebdf05b9`).

The columns map TOOL-MANIFEST.md fields the prototype catalog tracked
but v0.1.0's Tool model didn't carry:

  agent_owner   VARCHAR(64)  — "Only available to:" lines; NULL = fleet-wide
  best_for      TEXT         — use-case prose
  limitation    TEXT         — anti-pattern prose
  prefix        VARCHAR(32)  — tool naming pattern (e.g., firefox_*)
  transport     VARCHAR(32)  — per-tool transport (separate from Pack.transport)
  auth          VARCHAR(32)  — auth mechanism (api_key, oauth, jwt, ...)
  succeeded_by  VARCHAR(64)  — retirement lineage; plain slug reference

All are nullable. The catalog ingest script in Stage 1A item 7 populates
them from the live manifest; older rows (skills already in the DB before
this revision) carry NULL until reingested. `succeeded_by` is set by the
separate Stage 0 reconciliation slice, not by the manifest parser.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from core.db.models import PIN_STATUS_VALUES, Pack, Tool


# ---- Per-column round-trip ----------------------------------------------


class TestPerColumnRoundTrip:
    """Each new column persists the value byte-equal on read."""

    def test_agent_owner_round_trips(self, db_session: Session):
        t = Tool(slug="stripe", name="Stripe", agent_owner="alfred")
        db_session.add(t)
        db_session.commit()
        fetched = db_session.query(Tool).filter_by(slug="stripe").one()
        assert fetched.agent_owner == "alfred"

    def test_best_for_round_trips_prose(self, db_session: Session):
        t = Tool(
            slug="firefox-devtools",
            name="Firefox DevTools",
            best_for="Web scraping, testing, form automation, research",
        )
        db_session.add(t)
        db_session.commit()
        fetched = (
            db_session.query(Tool).filter_by(slug="firefox-devtools").one()
        )
        assert fetched.best_for == (
            "Web scraping, testing, form automation, research"
        )

    def test_limitation_round_trips_prose(self, db_session: Session):
        t = Tool(
            slug="firefox-devtools",
            name="Firefox DevTools",
            limitation=(
                "Cannot bypass anti-bot measures (shadow DOM, "
                "React dynamic UIs)"
            ),
        )
        db_session.add(t)
        db_session.commit()
        fetched = (
            db_session.query(Tool).filter_by(slug="firefox-devtools").one()
        )
        assert fetched.limitation == (
            "Cannot bypass anti-bot measures (shadow DOM, "
            "React dynamic UIs)"
        )

    def test_prefix_round_trips(self, db_session: Session):
        t = Tool(slug="firefox-devtools", name="Firefox DevTools", prefix="firefox_*")
        db_session.add(t)
        db_session.commit()
        fetched = (
            db_session.query(Tool).filter_by(slug="firefox-devtools").one()
        )
        assert fetched.prefix == "firefox_*"

    def test_transport_round_trips_per_tool(self, db_session: Session):
        """Tool.transport is per-tool metadata distinct from Pack.transport.
        Confirm both can carry different values on the same row without
        collision."""
        pack = Pack(slug="elevenlabs", name="ElevenLabs", transport="stdio")
        t = Tool(
            slug="elevenlabs-tts",
            name="ElevenLabs TTS",
            pack=pack,
            transport="stdio (uvx→python)",
        )
        db_session.add(t)
        db_session.commit()
        fetched = db_session.query(Tool).filter_by(slug="elevenlabs-tts").one()
        assert fetched.transport == "stdio (uvx→python)"
        assert fetched.pack.transport == "stdio"

    def test_auth_round_trips(self, db_session: Session):
        t = Tool(slug="mailerlite", name="MailerLite", auth="jwt")
        db_session.add(t)
        db_session.commit()
        fetched = db_session.query(Tool).filter_by(slug="mailerlite").one()
        assert fetched.auth == "jwt"

    def test_succeeded_by_round_trips_slug(self, db_session: Session):
        """succeeded_by is a plain slug string, NOT a foreign key — the
        recommendation engine reads it informationally to redirect
        queries for retired tools to their successors."""
        t = Tool(
            slug="mailerlite",
            name="MailerLite",
            lifecycle_state="retired",
            succeeded_by="ghl",
        )
        db_session.add(t)
        db_session.commit()
        fetched = db_session.query(Tool).filter_by(slug="mailerlite").one()
        assert fetched.succeeded_by == "ghl"


# ---- Defaults + partial inserts -----------------------------------------


class TestDefaultsAndPartialInserts:
    """Newly-inserted rows default every catalog-metadata column to NULL.
    Partial inserts preserve unspecified columns at NULL without coercing
    them to empty strings or falsey defaults."""

    def test_all_seven_columns_default_to_null(self, db_session: Session):
        t = Tool(slug="bare", name="bare")
        db_session.add(t)
        db_session.commit()
        fetched = db_session.query(Tool).filter_by(slug="bare").one()
        assert fetched.agent_owner is None
        assert fetched.best_for is None
        assert fetched.limitation is None
        assert fetched.prefix is None
        assert fetched.transport is None
        assert fetched.auth is None
        assert fetched.succeeded_by is None

    def test_partial_set_keeps_unspecified_columns_null(
        self, db_session: Session
    ):
        """A real ingest run will frequently set 3 of 7 fields on a given
        row (e.g., only agent_owner / transport / prefix appear in a
        particular manifest entry). The unset columns must read back as
        NULL, not as the empty string."""
        t = Tool(
            slug="memory",
            name="Semantic Memory",
            agent_owner="alfred",
            transport="stdio",
            prefix="memory_*",
        )
        db_session.add(t)
        db_session.commit()
        fetched = db_session.query(Tool).filter_by(slug="memory").one()
        assert fetched.agent_owner == "alfred"
        assert fetched.transport == "stdio"
        assert fetched.prefix == "memory_*"
        assert fetched.best_for is None
        assert fetched.limitation is None
        assert fetched.auth is None
        assert fetched.succeeded_by is None


# ---- Long prose round-trip ----------------------------------------------


class TestLongProseRoundTrip:
    """`best_for` and `limitation` are TEXT columns (no length limit). The
    manifest's prose entries can be multiple sentences; this confirms
    long values survive the round-trip without truncation."""

    def test_long_best_for_round_trips_intact(self, db_session: Session):
        long_prose = (
            "Web scraping, testing, form automation, and research workflows "
            "that need a real browser engine (anti-bot detection, JavaScript "
            "execution, form submissions). Pairs well with headless Firefox "
            "for stealth automation. Slower than HTTP-only tools (e.g., "
            "ripgrep, jq, curl) and not appropriate for static-content tasks "
            "where a lightweight tool would be faster and cheaper."
        )
        t = Tool(slug="x", name="x", best_for=long_prose)
        db_session.add(t)
        db_session.commit()
        fetched = db_session.query(Tool).filter_by(slug="x").one()
        assert fetched.best_for == long_prose

    def test_long_limitation_round_trips_intact(self, db_session: Session):
        long_prose = (
            "Cannot bypass shadow-DOM anti-bot measures, cannot interact "
            "with React-driven dynamic UIs that require synthetic events, "
            "and cannot navigate sites that gate behind CloudFlare's "
            "JavaScript challenge. For those workflows, use the Browser "
            "Control MCP server against Alfred's real Firefox ESR session."
        )
        t = Tool(slug="x", name="x", limitation=long_prose)
        db_session.add(t)
        db_session.commit()
        fetched = db_session.query(Tool).filter_by(slug="x").one()
        assert fetched.limitation == long_prose


# ---- Interaction with existing Tool columns -----------------------------


class TestCoexistenceWithExistingColumns:
    """The new columns must coexist with the prior Tool surface
    without unexpected side-effects: lifecycle_state, is_in_manifest,
    install_method, category, path, ambient_loading. (`is_active` was
    part of this surface before it was retired — DECISIONS D112.)"""

    def test_all_tool_columns_settable_in_one_insert(self, db_session: Session):
        pack = Pack(slug="elevenlabs", name="ElevenLabs", transport="stdio")
        t = Tool(
            slug="elevenlabs-tts",
            name="ElevenLabs TTS",
            description="Text-to-speech, voice synthesis, audio generation",
            tool_type="mcp",
            category="ai-services",
            install_method="mcp-server",
            install_method_provenance="mcp-server",
            is_in_manifest=True,
            lifecycle_state="loaded-on-boot",
            pack=pack,
            # Skills-specific (NULL for non-skill rows)
            path=None,
            ambient_loading=None,
            # New catalog metadata
            agent_owner="alfred",
            best_for="Voiceover production, course content audio",
            limitation="Do NOT use for conversation replies — Discord bot handles voice",
            prefix="elevenlabs_*",
            transport="stdio (uvx→python)",
            auth="api_key",
            succeeded_by=None,
        )
        db_session.add(t)
        db_session.commit()
        fetched = db_session.query(Tool).filter_by(slug="elevenlabs-tts").one()
        assert fetched.tool_type == "mcp"
        assert fetched.lifecycle_state == "loaded-on-boot"
        assert fetched.agent_owner == "alfred"
        assert fetched.transport == "stdio (uvx→python)"
        assert fetched.auth == "api_key"
        assert fetched.prefix == "elevenlabs_*"
        assert fetched.path is None
        assert fetched.ambient_loading is None

    def test_succeeded_by_unset_when_lifecycle_not_retired(
        self, db_session: Session
    ):
        """Defensive: a tool can have succeeded_by NULL regardless of
        lifecycle_state. The semantic constraint (succeeded_by populated
        only when retired) is operator-level policy, not a DB constraint.
        Confirm the schema doesn't enforce it."""
        t = Tool(
            slug="elevenlabs-tts",
            name="ElevenLabs TTS",
            lifecycle_state="loaded-on-boot",
            succeeded_by=None,
        )
        db_session.add(t)
        db_session.commit()
        fetched = db_session.query(Tool).filter_by(slug="elevenlabs-tts").one()
        assert fetched.lifecycle_state == "loaded-on-boot"
        assert fetched.succeeded_by is None

    def test_succeeded_by_settable_on_active_row_no_constraint(
        self, db_session: Session
    ):
        """Defensive: the schema permits succeeded_by alongside any
        lifecycle_state. Policy enforcement (succeeded_by + retired
        only) lives in the recommendation engine / ingest layer, not
        at the DB level."""
        t = Tool(
            slug="some-active",
            name="Some Active",
            lifecycle_state="used",
            succeeded_by="future-replacement",
        )
        db_session.add(t)
        db_session.commit()
        fetched = db_session.query(Tool).filter_by(slug="some-active").one()
        assert fetched.lifecycle_state == "used"
        assert fetched.succeeded_by == "future-replacement"


# ---- pin_status (Stage 1B reconciliation slice, Phase A — D77) ----------


class TestPinStatus:
    """`pin_status` — the operator-pin authority class (D77).
    `always-pinned` / `auto-managed`; NOT-NULL, defaults to
    `auto-managed`."""

    def test_pin_status_defaults_to_auto_managed(self, db_session: Session):
        """A row created without an explicit pin_status gets
        `auto-managed` — the Concierge-managed default. This is what
        the add-column migration's server_default backfills the
        existing catalog to."""
        t = Tool(slug="defaulted", name="Defaulted")
        db_session.add(t)
        db_session.commit()
        fetched = db_session.query(Tool).filter_by(slug="defaulted").one()
        assert fetched.pin_status == "auto-managed"

    def test_pin_status_round_trips_always_pinned(self, db_session: Session):
        """`always-pinned` persists byte-equal — the value the Stage 1B
        reconciliation sets on Alfred's semantic-memory MCP."""
        t = Tool(
            slug="semantic-memory-chromadb",
            name="semantic-memory-chromadb",
            lifecycle_state="loaded-on-boot",
            pin_status="always-pinned",
        )
        db_session.add(t)
        db_session.commit()
        fetched = (
            db_session.query(Tool)
            .filter_by(slug="semantic-memory-chromadb")
            .one()
        )
        assert fetched.pin_status == "always-pinned"

    def test_pin_status_values_constant_is_the_locked_pair(self):
        """Defensive-D24 values-pinning guard (D56): the D77-locked
        pair. A future edit changing the set trips this — the D24
        green-signal mechanic, requiring a deliberate forward-update."""
        assert PIN_STATUS_VALUES == ("always-pinned", "auto-managed")

    def test_pin_status_column_enum_built_from_constant(self):
        """Lock-step: the `pin_status` column's Enum is built from
        exactly `PIN_STATUS_VALUES` — the constant and the column
        cannot drift apart."""
        enum_values = tuple(Tool.__table__.c.pin_status.type.enums)
        assert enum_values == PIN_STATUS_VALUES
