"""Wiring tests for GET /partials/tool-registry — Day 10 Task 2.

Contracts under test:

1. **Catalog-empty branch** — fresh DB renders the catalog-empty
   designed state ("No tools catalogued yet…"). Filter-empty copy
   must NOT appear; this is a different condition.
2. **Filter-empty branch** — catalog has tools but the operator's
   filter excluded all of them. Renders the filter-empty designed
   state ("No tools match your search…") + the form with current
   filter values pre-filled so the operator can refine without
   retyping.
3. **Non-empty branch** — catalog has matching tools; renders
   cards-in-pack-groups with pack name + slug + each tool's name +
   slug + lifecycle-state badge + tool_type.
4. **Filter form HTMX wiring** — the form carries `hx-get`, the
   correct target, swap, and triggers (submit + change).
5. **Pack grouping** — tools group correctly by pack_slug; multiple
   packs render as separate sections.
6. **Filter pass-through** — the form values render with the
   submitted filter values pre-populated so operators don't lose
   context on a refresh.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from core.db.models import Pack, Tool
from core.db.session import get_db
from ui.app import create_app as create_ui_app


def _ui_client(db_session) -> TestClient:
    app = create_ui_app()
    app.dependency_overrides[get_db] = lambda: (yield db_session)
    return TestClient(app)


# ---- Branch 1: catalog-empty ---------------------------------------


class TestCatalogEmptyBranch:

    def test_renders_catalog_empty_copy(self, db_session):
        client = _ui_client(db_session)
        body = client.get("/partials/tool-registry").text
        assert "No tools catalogued yet" in body
        # The catalog-empty branch should NOT include the form (no
        # filter to refine when there's nothing in the catalog).
        assert "tool-registry--empty-catalog" in body

    def test_catalog_empty_distinct_from_filter_empty(self, db_session):
        """Confusing the two empty conditions is the bad-UX case the
        two-empty-state expansion was designed to prevent."""
        client = _ui_client(db_session)
        body = client.get("/partials/tool-registry").text
        assert "No tools match your search" not in body


# ---- Branch 2: filter-empty ----------------------------------------


class TestFilterEmptyBranch:

    def test_renders_filter_empty_copy_when_filter_excludes_all(
        self, db_session
    ):
        # Seed catalog with one tool; filter on a name that doesn't match
        db_session.add(
            Tool(slug="ripgrep", name="ripgrep", is_in_manifest=True)
        )
        db_session.commit()

        client = _ui_client(db_session)
        body = client.get(
            "/partials/tool-registry", params={"name_q": "nonexistent"}
        ).text
        assert "No tools match your search" in body
        assert "tool-registry--empty-filter" in body

    def test_filter_empty_distinct_from_catalog_empty(self, db_session):
        db_session.add(
            Tool(slug="ripgrep", name="ripgrep", is_in_manifest=True)
        )
        db_session.commit()

        client = _ui_client(db_session)
        body = client.get(
            "/partials/tool-registry", params={"name_q": "nonexistent"}
        ).text
        # Filter-empty branch must NOT include catalog-empty copy
        assert "No tools catalogued yet" not in body

    def test_filter_empty_preserves_filter_values_in_form(self, db_session):
        """Operator's current filter values render pre-filled so they
        can clear/refine without retyping."""
        db_session.add(
            Tool(slug="ripgrep", name="ripgrep", is_in_manifest=True)
        )
        db_session.commit()

        client = _ui_client(db_session)
        body = client.get(
            "/partials/tool-registry",
            params={"name_q": "nonexistent", "tool_type": "cli"},
        ).text
        # name_q value echoed back into the search input
        assert 'value="nonexistent"' in body
        # tool_type cli option marked selected
        assert 'value="cli" selected' in body


# ---- Branch 3: non-empty -------------------------------------------


class TestNonEmptyBranch:

    def _seed_two_packs(self, db_session) -> None:
        cli_pack = Pack(slug="cli-tools", name="CLI Tools")
        mcp_pack = Pack(slug="mcp-servers", name="MCP Servers")
        db_session.add_all([cli_pack, mcp_pack])
        db_session.flush()
        db_session.add_all(
            [
                Tool(
                    slug="ripgrep", name="ripgrep",
                    pack_id=cli_pack.id, tool_type="cli",
                    is_in_manifest=True,
                    install_method="brew",
                ),
                Tool(
                    slug="fd", name="fd",
                    pack_id=cli_pack.id, tool_type="cli",
                    is_in_manifest=True,
                ),
                Tool(
                    slug="brave-search", name="brave-search",
                    pack_id=mcp_pack.id, tool_type="mcp",
                    is_in_manifest=True,
                ),
            ]
        )
        db_session.commit()

    def test_renders_cards_in_pack_groups(self, db_session):
        self._seed_two_packs(db_session)
        client = _ui_client(db_session)
        body = client.get("/partials/tool-registry").text

        # Both pack headers render
        assert "CLI Tools" in body
        assert "MCP Servers" in body
        assert "(cli-tools)" in body
        assert "(mcp-servers)" in body

        # Each tool's name + slug + lifecycle-state badge + tool_type
        assert "ripgrep" in body
        assert "fd" in body
        assert "brave-search" in body
        # Lifecycle-state badges (default = discovered)
        assert "badge-discovered" in body
        # tool_type rendered
        assert "cli" in body
        assert "mcp" in body
        # install_method rendered when present
        assert "brew" in body

    def test_filter_form_hx_attributes_present(self, db_session):
        self._seed_two_packs(db_session)
        client = _ui_client(db_session)
        body = client.get("/partials/tool-registry").text
        assert 'hx-get="/partials/tool-registry"' in body
        assert 'hx-target="#tool-registry"' in body
        assert 'hx-swap="outerHTML"' in body
        assert 'hx-trigger="submit, change"' in body

    def test_filter_by_name_q_narrows_results(self, db_session):
        self._seed_two_packs(db_session)
        client = _ui_client(db_session)
        body = client.get(
            "/partials/tool-registry", params={"name_q": "ripgrep"}
        ).text
        assert "ripgrep" in body
        # fd and brave-search should not appear under this filter
        assert ">fd<" not in body
        assert "brave-search" not in body

    def test_filter_by_tool_type_narrows_results(self, db_session):
        self._seed_two_packs(db_session)
        client = _ui_client(db_session)
        body = client.get(
            "/partials/tool-registry", params={"tool_type": "mcp"}
        ).text
        # MCP pack tool present
        assert "brave-search" in body
        # CLI pack tools should be excluded under tool_type=mcp
        assert "ripgrep" not in body

    def test_empty_string_filter_treated_as_no_filter(self, db_session):
        """`?tool_type=` (empty) from the form's "All types" option
        should NOT match nothing — should match all tools."""
        self._seed_two_packs(db_session)
        client = _ui_client(db_session)
        body = client.get(
            "/partials/tool-registry", params={"tool_type": ""}
        ).text
        assert "ripgrep" in body
        assert "fd" in body
        assert "brave-search" in body


# ---- Pin-status badge (Stage 1B reconciliation slice, Phase A — D77) -----


class TestPinStatusBadge:
    """The pin-status badge (D77) renders alongside the lifecycle
    badge — but only for tools residing in `loaded-on-boot`, where
    pin status is meaningful (the at-a-glance operator-reserved vs.
    Concierge-managed distinction). Non-boot rows carry the
    `auto-managed` default inertly and show no pin badge.
    """

    def test_always_pinned_badge_shown_for_loaded_on_boot_tool(
        self, db_session
    ):
        db_session.add(
            Tool(
                slug="semantic-memory-chromadb",
                name="semantic-memory-chromadb",
                is_in_manifest=True,
                lifecycle_state="loaded-on-boot",
                pin_status="always-pinned",
            )
        )
        db_session.commit()
        client = _ui_client(db_session)
        body = client.get("/partials/tool-registry").text
        assert "badge-pin-always-pinned" in body
        assert "always-pinned" in body

    def test_auto_managed_badge_shown_for_loaded_on_boot_tool(
        self, db_session
    ):
        db_session.add(
            Tool(
                slug="firefox-devtools",
                name="firefox-devtools",
                is_in_manifest=True,
                lifecycle_state="loaded-on-boot",
                # pin_status omitted — defaults to auto-managed
            )
        )
        db_session.commit()
        client = _ui_client(db_session)
        body = client.get("/partials/tool-registry").text
        assert "badge-pin-auto-managed" in body

    def test_no_pin_badge_for_non_boot_tool(self, db_session):
        """The contrast: a `discovered` tool carries the `auto-managed`
        default but is not boot-resident, so no pin badge renders —
        pin status is not surfaced where it has no meaning."""
        db_session.add(
            Tool(
                slug="ripgrep",
                name="ripgrep",
                is_in_manifest=True,
                lifecycle_state="discovered",
            )
        )
        db_session.commit()
        client = _ui_client(db_session)
        body = client.get("/partials/tool-registry").text
        # The lifecycle badge renders; the pin badge does not.
        assert "badge-discovered" in body
        assert "badge-pin-" not in body
