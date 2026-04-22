"""Tests for core.recommend.prompt — composition determinism +
adapter-preamble structure.

Per DECISIONS [2026-04-22 07:26], the composed system prompt has
five observable blocks in this order:

  1. Concierge adapter preamble
  2. X3 tool-awareness fragment (verbatim)
  3. X4 tool-recommendation fragment (verbatim)
  4. X6 tool-discovery fragment (verbatim)
  5. X7-A tool-lifecycle weekly-review fragment (verbatim)
  6. JSON output envelope

Test surface asserts that structure, determinism, and the
three-state memory sentinel. No semantic quality tested here.
"""
from __future__ import annotations

from core.memory import MemoryHit
from core.prompts import (
    TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD,
    TOOL_DISCOVERY_PROTOCOL__FROM_TOOL_DISCOVERY_SKILL,
    TOOL_LIFECYCLE_WEEKLY_REVIEW_PROTOCOL__FROM_TOOL_LIFECYCLE_SKILL,
    TOOL_RECOMMENDATION_PROTOCOL__FROM_TOOL_RECOMMENDATION_MD,
)
from core.recommend.prompt import (
    BLOCK_SEPARATOR,
    CONCIERGE_ADAPTER_PREAMBLE,
    CatalogToolView,
    JSON_OUTPUT_ENVELOPE,
    compose_recommendation_prompt,
)


# ---- Fixtures ------------------------------------------------------------


def _tool(
    slug: str,
    name: str,
    *,
    description: str | None = None,
    category: str | None = None,
    pack_slug: str | None = None,
    is_in_manifest: bool = True,
    is_active: bool = True,
) -> CatalogToolView:
    return CatalogToolView(
        slug=slug,
        name=name,
        description=description,
        category=category,
        pack_slug=pack_slug,
        is_in_manifest=is_in_manifest,
        is_active=is_active,
    )


def _sample_catalog() -> list[CatalogToolView]:
    return [
        _tool(
            "csvstat",
            "csvstat",
            description="Summary stats for CSV files",
            category="data",
            pack_slug="csvkit",
        ),
        _tool(
            "pandas",
            "pandas",
            description="Data analysis library",
            category="data",
            is_in_manifest=True,
            is_active=False,  # dormant
        ),
        _tool(
            "ripgrep",
            "ripgrep",
            category="search",
            is_in_manifest=False,
            is_active=False,  # retired
        ),
        _tool(
            "duckdb",
            "DuckDB",
            is_in_manifest=False,
            is_active=True,  # pending (not in manifest, actively loaded)
        ),
    ]


def _hit(text: str, sim: float = 0.9, tags: tuple[str, ...] = ("tool-selection",)) -> MemoryHit:
    return MemoryHit(
        id="mem_" + text[:6],
        text=text,
        similarity=sim,
        tags=tags,
        importance="normal",
        source="test",
        created_at="2026-04-20T12:00:00",
    )


# ---- Determinism ---------------------------------------------------------


class TestDeterminism:
    def test_identical_inputs_produce_byte_identical_output(self):
        catalog = _sample_catalog()
        hits = [_hit("user prefers lightweight CLIs"), _hit("csvstat used 3 times", sim=0.7)]

        a = compose_recommendation_prompt(
            task="analyze this CSV",
            catalog=catalog,
            memory_hits=hits,
            cwd="/home/lewie",
            task_hint="data-analysis",
            active_tools=["pandas"],
        )
        b = compose_recommendation_prompt(
            task="analyze this CSV",
            catalog=catalog,
            memory_hits=hits,
            cwd="/home/lewie",
            task_hint="data-analysis",
            active_tools=["pandas"],
        )
        assert a.system == b.system
        assert a.user == b.user

    def test_catalog_ordering_does_not_affect_output(self):
        catalog_forward = _sample_catalog()
        catalog_reversed = list(reversed(_sample_catalog()))

        a = compose_recommendation_prompt(
            task="t", catalog=catalog_forward, memory_hits=None
        )
        b = compose_recommendation_prompt(
            task="t", catalog=catalog_reversed, memory_hits=None
        )
        # Catalog sort is deterministic by slug — input order must
        # not leak into output bytes. This catches the common
        # mistake of rendering catalog in DB-row-insertion order.
        assert a.user == b.user


# ---- Block structure -----------------------------------------------------


class TestSystemPromptStructure:
    def test_preamble_appears_first(self):
        p = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None
        )
        assert p.system.startswith(CONCIERGE_ADAPTER_PREAMBLE)

    def test_envelope_appears_last(self):
        p = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None
        )
        assert p.system.endswith(JSON_OUTPUT_ENVELOPE)

    def test_all_four_fragments_present_verbatim(self):
        p = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None
        )
        # Fragments are rstripped during composition so the
        # separator line shows; verbatim-ness is the body content.
        assert TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD.rstrip() in p.system
        assert TOOL_RECOMMENDATION_PROTOCOL__FROM_TOOL_RECOMMENDATION_MD.rstrip() in p.system
        assert TOOL_DISCOVERY_PROTOCOL__FROM_TOOL_DISCOVERY_SKILL.rstrip() in p.system
        assert TOOL_LIFECYCLE_WEEKLY_REVIEW_PROTOCOL__FROM_TOOL_LIFECYCLE_SKILL.rstrip() in p.system

    def test_block_order_preamble_then_fragments_then_envelope(self):
        p = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None
        )
        pos_preamble = p.system.find(CONCIERGE_ADAPTER_PREAMBLE)
        pos_x3 = p.system.find(TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD.rstrip())
        pos_x4 = p.system.find(
            TOOL_RECOMMENDATION_PROTOCOL__FROM_TOOL_RECOMMENDATION_MD.rstrip()
        )
        pos_x6 = p.system.find(
            TOOL_DISCOVERY_PROTOCOL__FROM_TOOL_DISCOVERY_SKILL.rstrip()
        )
        pos_x7 = p.system.find(
            TOOL_LIFECYCLE_WEEKLY_REVIEW_PROTOCOL__FROM_TOOL_LIFECYCLE_SKILL.rstrip()
        )
        pos_envelope = p.system.find(JSON_OUTPUT_ENVELOPE)

        assert pos_preamble != -1
        assert pos_envelope != -1
        # Strict ordering.
        assert pos_preamble < pos_x3 < pos_x4 < pos_x6 < pos_x7 < pos_envelope

    def test_block_separators_at_each_junction(self):
        """Verify `BLOCK_SEPARATOR` actually sits at each of the five
        junctions between the six blocks. A plain count-based check
        doesn't work because the X7-A fragment contains internal
        `---\\n` separators from its source markdown. Checking the
        specific junction positions is stricter and unambiguous.
        """
        p = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None
        )
        # Junction 1: preamble → X3
        preamble_end = p.system.find(CONCIERGE_ADAPTER_PREAMBLE) + len(
            CONCIERGE_ADAPTER_PREAMBLE
        )
        assert (
            p.system[preamble_end : preamble_end + len(BLOCK_SEPARATOR)]
            == BLOCK_SEPARATOR
        )

        # Each fragment is rstripped before the separator. We confirm
        # the separator immediately precedes the start of the next
        # block at the first-occurrence position of each fragment.
        def junction_before(needle: str) -> None:
            pos = p.system.find(needle)
            assert pos != -1
            assert (
                p.system[pos - len(BLOCK_SEPARATOR) : pos] == BLOCK_SEPARATOR
            ), f"missing BLOCK_SEPARATOR before block starting with {needle[:40]!r}"

        junction_before(TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD.rstrip())
        junction_before(TOOL_RECOMMENDATION_PROTOCOL__FROM_TOOL_RECOMMENDATION_MD.rstrip())
        junction_before(TOOL_DISCOVERY_PROTOCOL__FROM_TOOL_DISCOVERY_SKILL.rstrip())
        junction_before(
            TOOL_LIFECYCLE_WEEKLY_REVIEW_PROTOCOL__FROM_TOOL_LIFECYCLE_SKILL.rstrip()
        )
        junction_before(JSON_OUTPUT_ENVELOPE)

    def test_preamble_overrides_opencaw_infrastructure(self):
        """The preamble must actually address the three coupling
        surfaces (agent names, infra paths, MCP tool calls). This
        keeps someone from silently removing the overrides during
        a future edit.
        """
        assert "Alfred" in CONCIERGE_ADAPTER_PREAMBLE
        assert "satiety-pipeline" in CONCIERGE_ADAPTER_PREAMBLE
        assert "memory__memory_search" in CONCIERGE_ADAPTER_PREAMBLE
        assert "JSON schema" in CONCIERGE_ADAPTER_PREAMBLE


# ---- User message rendering ----------------------------------------------


class TestUserMessage:
    def test_task_verbatim(self):
        p = compose_recommendation_prompt(
            task="analyze this 5GB CSV quickly",
            catalog=[],
            memory_hits=None,
        )
        assert "analyze this 5GB CSV quickly" in p.user

    def test_task_appears_before_context(self):
        p = compose_recommendation_prompt(
            task="T", catalog=[], memory_hits=None
        )
        assert p.user.index("# Task") < p.user.index("# Context")
        assert p.user.index("# Context") < p.user.index("# Available tools")
        assert p.user.index("# Available tools") < p.user.index("# Relevant memory")

    def test_state_annotations_for_all_four_states(self):
        p = compose_recommendation_prompt(
            task="t", catalog=_sample_catalog(), memory_hits=None
        )
        assert "[active]" in p.user
        assert "[dormant]" in p.user
        assert "[pending]" in p.user
        assert "[retired]" in p.user

    def test_catalog_renders_slug_and_name(self):
        p = compose_recommendation_prompt(
            task="t", catalog=_sample_catalog(), memory_hits=None
        )
        assert "**csvstat**" in p.user
        assert "csvstat" in p.user  # name also present
        assert "(pack: csvkit)" in p.user

    def test_catalog_empty_sentinel(self):
        p = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None
        )
        assert "(catalog is empty)" in p.user

    def test_cwd_and_hint_defaults_when_absent(self):
        p = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None
        )
        assert "(caller did not provide a working directory)" in p.user
        assert "(no caller-provided category hint)" in p.user
        assert "(caller did not report active-tool state)" in p.user

    def test_cwd_and_hint_when_present(self):
        p = compose_recommendation_prompt(
            task="t",
            catalog=[],
            memory_hits=None,
            cwd="/home/lewie",
            task_hint="data-analysis",
            active_tools=["pandas", "csvstat"],
        )
        assert "/home/lewie" in p.user
        assert "data-analysis" in p.user
        assert "csvstat" in p.user and "pandas" in p.user

    def test_empty_active_tools_list_distinct_from_none(self):
        p_none = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None, active_tools=None
        )
        p_empty = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None, active_tools=[]
        )
        assert "(caller did not report active-tool state)" in p_none.user
        assert "(no tools currently active)" in p_empty.user
        assert p_none.user != p_empty.user


# ---- Memory tri-state (critical adversarial surface) --------------------


class TestMemoryTriState:
    def test_memory_unavailable_sentinel(self):
        """Outage path: `memory_hits=None` must render the exact
        sentinel the service uses for the DEBUG-log marker.
        """
        p = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None
        )
        assert "(memory unavailable)" in p.user

    def test_no_relevant_memory_sentinel(self):
        """Healthy-but-empty path: `memory_hits=[]` must render the
        distinct sentinel that distinguishes it from outage.
        """
        p = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=[]
        )
        assert "(no relevant memory)" in p.user
        assert "(memory unavailable)" not in p.user

    def test_populated_memory_renders_hits(self):
        p = compose_recommendation_prompt(
            task="t",
            catalog=[],
            memory_hits=[_hit("user prefers lightweight CLIs")],
        )
        assert "user prefers lightweight CLIs" in p.user
        assert "(memory unavailable)" not in p.user
        assert "(no relevant memory)" not in p.user

    def test_three_memory_states_are_all_distinct_outputs(self):
        """If any two of the three memory states produced identical
        user-message bytes, an operator reading logs could not
        visually distinguish them. This assertion is the adversarial
        guard for that failure mode.
        """
        p_none = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None
        )
        p_empty = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=[]
        )
        p_hits = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=[_hit("x")]
        )
        assert p_none.user != p_empty.user
        assert p_empty.user != p_hits.user
        assert p_none.user != p_hits.user

    def test_memory_hits_include_similarity_and_tags(self):
        p = compose_recommendation_prompt(
            task="t",
            catalog=[],
            memory_hits=[_hit("x", sim=0.812, tags=("tag-a", "tag-b"))],
        )
        assert "0.812" in p.user
        assert "tag-a" in p.user
        assert "tag-b" in p.user
