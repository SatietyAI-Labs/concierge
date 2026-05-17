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

import logging

import pytest

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
    lifecycle_state: str | None = "loaded-on-boot",
) -> CatalogToolView:
    return CatalogToolView(
        slug=slug,
        name=name,
        description=description,
        category=category,
        pack_slug=pack_slug,
        is_in_manifest=is_in_manifest,
        lifecycle_state=lifecycle_state,
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
            lifecycle_state="discovered",  # dormant
        ),
        _tool(
            "ripgrep",
            "ripgrep",
            category="search",
            is_in_manifest=False,
            lifecycle_state="retired",
        ),
        _tool(
            "duckdb",
            "DuckDB",
            is_in_manifest=False,
            lifecycle_state="pending",
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
        # Ordering chain extended for the recommend-prompt wiring slice:
        # when per-agent identity is present, the `# Calling agent
        # identity` section slots between `# Context` and `# Available
        # tools`. Positive-ordering assertion (not a closed-set
        # exhaustiveness guard — the user-prompt section set has no
        # exhaustive consumer; see DECISIONS item-8 D24 judgment).
        p_ident = compose_recommendation_prompt(
            task="T",
            catalog=[],
            memory_hits=None,
            agent_id="scout",
            agent_identity="Scout — content-prep worker.",
        )
        assert (
            p_ident.user.index("# Task")
            < p_ident.user.index("# Context")
            < p_ident.user.index("# Calling agent identity")
            < p_ident.user.index("# Available tools")
            < p_ident.user.index("# Relevant memory")
        )

    def test_state_annotations_render_canonical_lifecycle_state(self):
        # `_sample_catalog` sets each view's canonical `lifecycle_state`;
        # the row renders `[<lifecycle_state>]`. The legacy four-state
        # `_tool_state` derivation was removed with `is_active` (D112).
        p = compose_recommendation_prompt(
            task="t", catalog=_sample_catalog(), memory_hits=None
        )
        assert "[loaded-on-boot]" in p.user
        assert "[discovered]" in p.user
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


class TestSkillsCatalogRendering:
    """Skills are the fourth peer catalog category — DECISIONS
    [2026-04-23]. They render differently from MCP/CLI/HTTP because
    they're ambient-loaded (no install step) and carry a path to
    their SKILL.md."""

    def _skill(
        self,
        slug: str,
        *,
        ambient_loading: bool = True,
        path: str = "/mnt/skills/public/sk/SKILL.md",
        description: str | None = None,
    ) -> CatalogToolView:
        return CatalogToolView(
            slug=slug,
            name=slug,
            description=description,
            category=None,
            pack_slug=None,
            is_in_manifest=True,
            tool_type="skill",
            install_method=None,
            path=path,
            ambient_loading=ambient_loading,
        )

    def test_skill_row_tagged_as_skill_not_mcp_state(self):
        p = compose_recommendation_prompt(
            task="t",
            catalog=[self._skill("update-config")],
            memory_hits=None,
        )
        # Skills render with <skill> tag — not [active]/[dormant] state
        assert "<skill>" in p.user
        assert "**update-config**" in p.user

    def test_skill_row_exposes_ambient_loading_flag(self):
        p = compose_recommendation_prompt(
            task="t",
            catalog=[self._skill("update-config", ambient_loading=True)],
            memory_hits=None,
        )
        assert "[ambient]" in p.user

    def test_skill_row_exposes_path(self):
        p = compose_recommendation_prompt(
            task="t",
            catalog=[
                self._skill(
                    "update-config",
                    path="/mnt/skills/public/update-config/SKILL.md",
                )
            ],
            memory_hits=None,
        )
        assert "/mnt/skills/public/update-config/SKILL.md" in p.user

    def test_skill_row_has_no_install_annotation(self):
        """Skills are ambient, not installed — render should omit install=."""
        p = compose_recommendation_prompt(
            task="t",
            catalog=[self._skill("update-config")],
            memory_hits=None,
        )
        # The line for this skill should not contain install=...
        skill_line = next(
            line for line in p.user.splitlines()
            if "**update-config**" in line
        )
        assert "install=" not in skill_line

    def test_mixed_catalog_mcp_and_skill_render_differently(self):
        """Both categories coexist and keep their distinguishing tags."""
        mcp_tool = CatalogToolView(
            slug="memory-store",
            name="memory_store",
            description=None,
            category="ai-services",
            pack_slug="memory-mcp",
            is_in_manifest=True,
            tool_type="mcp",
            install_method="mcp-server",
            lifecycle_state="loaded-on-boot",
        )
        p = compose_recommendation_prompt(
            task="t",
            catalog=[mcp_tool, self._skill("update-config")],
            memory_hits=None,
        )
        assert "<mcp>" in p.user
        assert "<skill>" in p.user
        assert "install=mcp-server" in p.user
        # Skill line stays free of install=
        skill_line = next(
            line for line in p.user.splitlines()
            if "**update-config**" in line
        )
        assert "install=" not in skill_line

    def test_on_demand_skill_rendered_distinctly_from_ambient(self):
        p = compose_recommendation_prompt(
            task="t",
            catalog=[self._skill("on-demand-sk", ambient_loading=False)],
            memory_hits=None,
        )
        assert "[on-demand]" in p.user
        assert "[ambient]" not in p.user


class TestIdentityBlockPosition:
    """Fix Day 3 Fork 4 ruling: the identity block inserts between the
    adapter preamble and the X3 tool-awareness fragment — right after
    role-setting, before the behavioral protocols. Absent/empty
    identity collapses the block entirely."""

    def test_identity_block_appears_between_preamble_and_x3(self):
        identity_text = "Loaded-on-boot: csvkit (cli), ripgrep (cli)"
        p = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None, identity=identity_text,
        )
        # Preamble first
        preamble_idx = p.system.index(CONCIERGE_ADAPTER_PREAMBLE)
        # Identity block with header + content
        identity_idx = p.system.index("# Operator identity")
        identity_content_idx = p.system.index(identity_text)
        # X3 fragment after identity
        x3_idx = p.system.index(
            TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD.rstrip()
        )
        assert preamble_idx < identity_idx < identity_content_idx < x3_idx

    def test_identity_none_collapses_block(self):
        p_none = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None, identity=None,
        )
        assert "# Operator identity" not in p_none.system

    def test_identity_empty_string_collapses_block(self):
        p_empty = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None, identity="",
        )
        assert "# Operator identity" not in p_empty.system

    def test_identity_whitespace_only_collapses_block(self):
        p_ws = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None, identity="   \n\t  ",
        )
        assert "# Operator identity" not in p_ws.system

    def test_empty_identity_prompt_byte_identical_to_pre_identity_composition(
        self,
    ):
        """Regression guard: absent identity must produce the same
        system prompt as before Fix Day 3 Task 7 landed. Otherwise
        prompt-hash-stability tests upstream would falsely detect
        drift."""
        p_none = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None, identity=None,
        )
        p_default = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None,
        )
        assert p_none.system == p_default.system


class TestLifecycleStateRendering:
    """Fix Day 3 Task 3: stored `lifecycle_state` is the canonical state
    label for MCP/CLI/HTTP rendering. When a view carries no
    `lifecycle_state` (None), `_render_standard_row` logs a WARN naming
    the slug and renders the literal `[unknown]` state. The
    `Tool.lifecycle_state` column is NOT-NULL so a DB-sourced view
    always carries it; the WARN is cheap detection for a malformed
    directly-constructed view. The legacy `(is_in_manifest, is_active)`
    `_tool_state` fallback was removed with `is_active` (DECISIONS D112)."""

    def _row(self, slug: str, *, lifecycle_state=None) -> CatalogToolView:
        return CatalogToolView(
            slug=slug,
            name=slug,
            description=None,
            category=None,
            pack_slug=None,
            is_in_manifest=True,
            tool_type="cli",
            lifecycle_state=lifecycle_state,
        )

    def test_canonical_path_renders_stored_lifecycle_state(self):
        p = compose_recommendation_prompt(
            task="t",
            catalog=[self._row("csvkit", lifecycle_state="loaded-on-boot")],
            memory_hits=None,
        )
        assert "[loaded-on-boot]" in p.user
        # Old four-state vocab should NOT appear
        assert "[active]" not in p.user

    def test_all_five_canonical_states_render(self):
        catalog = [
            self._row("a-discovered", lifecycle_state="discovered"),
            self._row("b-pending", lifecycle_state="pending"),
            self._row("c-used", lifecycle_state="used"),
            self._row("d-loaded", lifecycle_state="loaded-on-boot"),
            self._row("e-retired", lifecycle_state="retired"),
        ]
        p = compose_recommendation_prompt(
            task="t", catalog=catalog, memory_hits=None
        )
        for state in (
            "discovered", "pending", "used", "loaded-on-boot", "retired"
        ):
            assert f"[{state}]" in p.user, f"missing [{state}] in output"

    def test_missing_lifecycle_state_renders_unknown_and_logs_warn(
        self, caplog: pytest.LogCaptureFixture
    ):
        row = self._row("legacy-row", lifecycle_state=None)
        with caplog.at_level(logging.WARNING, logger="core.recommend.prompt"):
            p = compose_recommendation_prompt(
                task="t", catalog=[row], memory_hits=None
            )
        # No lifecycle_state → the literal `[unknown]` state label
        assert "[unknown]" in p.user
        # WARN log fires naming the slug
        warns = [
            r for r in caplog.records
            if "lifecycle_state_missing" in r.message
        ]
        assert len(warns) == 1
        assert "legacy-row" in warns[0].message

    def test_mixed_catalog_canonical_and_fallback_exercise_both_paths(
        self, caplog: pytest.LogCaptureFixture
    ):
        catalog = [
            self._row("canonical", lifecycle_state="loaded-on-boot"),
            self._row("legacy", lifecycle_state=None),
        ]
        with caplog.at_level(logging.WARNING, logger="core.recommend.prompt"):
            p = compose_recommendation_prompt(
                task="t", catalog=catalog, memory_hits=None
            )
        assert "[loaded-on-boot]" in p.user  # canonical
        assert "[unknown]" in p.user  # missing-lifecycle_state path
        warns = [
            r for r in caplog.records
            if "lifecycle_state_missing" in r.message
        ]
        # Exactly one — only the legacy row triggers the fallback
        assert len(warns) == 1
        assert "legacy" in warns[0].message
        assert "canonical" not in warns[0].message


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


class TestSideObservationsPromptInstruction:
    """Fix Day 4 Task 3: JSON_OUTPUT_ENVELOPE must instruct Opus on
    the two Fork C trigger categories. These tests are anchor-phrase
    checks; they protect the instruction from accidentally losing
    either trigger when the envelope text is refactored.
    """

    def test_envelope_mentions_side_observations_field(self):
        p = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None
        )
        assert "side_observations" in p.system

    def test_envelope_names_retired_tool_overlap_category(self):
        """Fork C category (a): retired-tool overlap. The phrase
        'Retired-tool overlap' and the `[retired]` anchor must both
        appear so Opus has a concrete trigger bar.
        """
        p = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None
        )
        assert "Retired-tool overlap" in p.system
        assert "[retired]" in p.system

    def test_envelope_names_idle_loaded_on_boot_category(self):
        """Fork C category (c): idle loaded-on-boot tool. Anchor
        phrases 'Idle loaded-on-boot' and `[loaded-on-boot]` pin the
        category into the prompt.
        """
        p = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None
        )
        assert "Idle loaded-on-boot" in p.system
        assert "[loaded-on-boot]" in p.system

    def test_envelope_caps_at_two_observations(self):
        """Prompt instructs at most two entries; validator enforces
        the cap as a drift signal. Both surfaces reference the same
        number — if the prompt drops the cap without updating the
        validator, this guard fires first.
        """
        p = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None
        )
        assert "at most two" in p.system

    def test_envelope_permits_silence(self):
        """Opus must be told explicitly that omitting the key / empty
        list is correct behavior — otherwise it fills in low-signal
        observations to feel 'complete.'
        """
        p = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None
        )
        # Anchor phrases that permit silence without sentinel drift.
        assert "omit the key" in p.system
        assert "silence is correct" in p.system


# ---- Stage 1A item 3 — agent_id context line -----------------------------


class TestAgentIdContext:
    """`agent_id` renders as a fourth line in the user prompt's
    `# Context` block. Symmetric with cwd / task_hint / active_tools:
    line always present, sentinel when caller omits.

    Mechanism contract (per Stage 1A item 3 plan-surface):
    - When set: `"- Calling agent: <id>"` appears
    - When None / whitespace-only: `"- Calling agent: (no caller-provided agent identifier)"`
      appears (sentinel form mirrors task_hint's `(no caller-provided ...)` shape)
    - Determinism: identical inputs including agent_id produce
      byte-identical `system` AND `user` output across repeated calls
    - Position: under `# Context`, before `# Available tools`
    """

    def test_agent_id_renders_in_context_block(self):
        p = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None, agent_id="scout"
        )
        assert "- Calling agent: scout" in p.user

    def test_agent_id_appears_in_context_section(self):
        """Position invariant: the `Calling agent` line sits inside the
        `# Context` block, between `# Context` and `# Available tools`.
        """
        p = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None, agent_id="bridge"
        )
        ctx_pos = p.user.index("# Context")
        agent_pos = p.user.index("- Calling agent:")
        avail_pos = p.user.index("# Available tools")
        assert ctx_pos < agent_pos < avail_pos

    def test_agent_id_none_renders_sentinel(self):
        """Default `agent_id=None` must still render the line with the
        sentinel — same shape as cwd/task_hint/active_tools defaults.
        Sentinel form `(no caller-provided agent identifier)` mirrors
        task_hint's `(no caller-provided category hint)` phrasing.
        """
        p = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None
        )
        assert "- Calling agent: (no caller-provided agent identifier)" in p.user

    def test_agent_id_whitespace_only_collapses_to_sentinel(self):
        """Defensive: a whitespace-only `agent_id` collapses to the
        sentinel rather than rendering an empty line. Same defensive
        posture as `_render_identity_block` uses for the operator-
        identity string.
        """
        p = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None, agent_id="   "
        )
        assert "- Calling agent: (no caller-provided agent identifier)" in p.user

    def test_agent_id_stripped_when_padded(self):
        """A padded `agent_id` ("  scout  ") renders the stripped value
        — matches identity-block stripping; prevents whitespace from
        leaking into per-call prompt hashes.
        """
        p = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None, agent_id="  scout  "
        )
        # Exact: line renders the stripped value with no surrounding spaces.
        assert "- Calling agent: scout\n" in p.user
        # Negative: the unstripped form must not survive.
        assert "- Calling agent:   scout  " not in p.user

    def test_agent_id_determinism_across_calls(self):
        """Byte-equality of BOTH system and user prompts across two
        identical-input calls including `agent_id`. The determinism
        contract documented in `compose_recommendation_prompt`'s
        docstring applies to the new param too — same proof as
        `TestDeterminism.test_identical_inputs_produce_byte_identical_output`
        applied with `agent_id` set.
        """
        catalog = _sample_catalog()
        a = compose_recommendation_prompt(
            task="analyze this CSV",
            catalog=catalog,
            memory_hits=None,
            cwd="/home/lewie",
            task_hint="data-analysis",
            active_tools=["pandas"],
            agent_id="scout",
        )
        b = compose_recommendation_prompt(
            task="analyze this CSV",
            catalog=catalog,
            memory_hits=None,
            cwd="/home/lewie",
            task_hint="data-analysis",
            active_tools=["pandas"],
            agent_id="scout",
        )
        assert a.system == b.system
        assert a.user == b.user

    def test_agent_id_changes_user_prompt_bytes(self):
        """Different `agent_id` values produce different user-prompt
        bytes. This is what gives the recommendation engine the
        per-agent signal — without observable bytes diverging in the
        prompt, agent_id would be a no-op pass-through.
        """
        a = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None, agent_id="scout"
        )
        b = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None, agent_id="bridge"
        )
        assert a.user != b.user
        # System prompt is agent-agnostic — it stays byte-identical.
        assert a.system == b.system

    def test_agent_id_does_not_leak_into_system_prompt(self):
        """The agent_id signal belongs in the user message, not in the
        system prompt — the system prompt is the agent-agnostic
        protocol surface. A caller-specific identifier landing in the
        system block would defeat prompt-caching once the service
        wires it in.
        """
        p = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None, agent_id="scout"
        )
        assert "scout" not in p.system


# ---- Recommend-prompt wiring slice — per-agent identity section ----------


class TestAgentIdentitySection:
    """`agent_identity` renders as a `# Calling agent identity` section
    in the user prompt, between `# Context` and `# Available tools`.

    This is the calling agent's migrated identity notes — the text
    `MemoryClient.identity_get_agent(agent_id)` returns. It differs
    from the operator-identity block (`identity`) in two ways:

    - It lives in the *user* prompt, not the system prompt: it varies
      by `agent_id`, and the system prompt is the agent-agnostic
      protocol surface (`test_*_does_not_leak_into_system_prompt`).
    - Absent/empty `agent_identity` collapses the section *entirely*
      (header included) — the user prompt is byte-identical to a call
      without per-agent identity. This is the load-bearing invariant
      (`test_empty_agent_identity_user_prompt_byte_identical`).
    """

    _IDENTITY = (
        "Scout — content-prep worker. Drafts LinkedIn posts; hands "
        "finished drafts to Dispatch. Prefers ripgrep for code search."
    )

    def test_agent_identity_renders_section(self):
        p = compose_recommendation_prompt(
            task="t",
            catalog=[],
            memory_hits=None,
            agent_id="scout",
            agent_identity=self._IDENTITY,
        )
        assert "# Calling agent identity" in p.user
        assert self._IDENTITY in p.user

    def test_agent_identity_positioned_between_context_and_available_tools(
        self,
    ):
        """Position invariant: the section sits after the `# Context`
        block and before `# Available tools` — it expands on the
        `- Calling agent:` line.
        """
        p = compose_recommendation_prompt(
            task="t",
            catalog=[],
            memory_hits=None,
            agent_id="bridge",
            agent_identity=self._IDENTITY,
        )
        ctx_pos = p.user.index("# Context")
        calling_agent_pos = p.user.index("- Calling agent:")
        section_pos = p.user.index("# Calling agent identity")
        avail_pos = p.user.index("# Available tools")
        assert ctx_pos < calling_agent_pos < section_pos < avail_pos

    def test_agent_identity_none_collapses_section(self):
        p = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None, agent_identity=None
        )
        assert "# Calling agent identity" not in p.user

    def test_agent_identity_empty_string_collapses_section(self):
        p = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None, agent_identity=""
        )
        assert "# Calling agent identity" not in p.user

    def test_agent_identity_whitespace_only_collapses_section(self):
        """Defensive: a whitespace-only `agent_identity` collapses the
        section rather than rendering an empty header — same posture
        as `_render_identity_block` / `_render_agent_id`.
        """
        p = compose_recommendation_prompt(
            task="t",
            catalog=[],
            memory_hits=None,
            agent_identity="   \n\t  ",
        )
        assert "# Calling agent identity" not in p.user

    def test_agent_identity_stripped_when_padded(self):
        """A padded `agent_identity` renders the stripped content — no
        leading/trailing whitespace leaks into the section body.
        """
        p = compose_recommendation_prompt(
            task="t",
            catalog=[],
            memory_hits=None,
            agent_id="scout",
            agent_identity="  Scout — content-prep worker.  ",
        )
        assert (
            "# Calling agent identity\n\nScout — content-prep worker.\n\n"
            in p.user
        )

    def test_empty_agent_identity_user_prompt_byte_identical(self):
        """LOAD-BEARING INVARIANT. When `agent_identity` is absent /
        None / empty / whitespace-only, the composed user prompt is
        byte-identical to a call that never passed the kwarg, and the
        system prompt is unconditionally unchanged. This is what
        guarantees the wiring is a pure no-op until per-agent identity
        actually exists — mirrors the operator-identity path's
        `test_empty_identity_prompt_byte_identical_to_pre_identity_composition`.
        """
        baseline = compose_recommendation_prompt(
            task="t",
            catalog=_sample_catalog(),
            memory_hits=None,
            cwd="/home/lewie",
            task_hint="data-analysis",
            active_tools=["pandas"],
            agent_id="scout",
        )
        for collapsed in (None, "", "   \n\t  "):
            p = compose_recommendation_prompt(
                task="t",
                catalog=_sample_catalog(),
                memory_hits=None,
                cwd="/home/lewie",
                task_hint="data-analysis",
                active_tools=["pandas"],
                agent_id="scout",
                agent_identity=collapsed,
            )
            assert p.user == baseline.user, (
                f"agent_identity={collapsed!r} must leave the user "
                f"prompt byte-identical"
            )
            assert p.system == baseline.system

    def test_agent_identity_does_not_leak_into_system_prompt(self):
        """Per-agent identity is caller-specific — it belongs in the
        user message. A populated `agent_identity` must leave the
        system prompt byte-identical to a call without it.
        """
        p_with = compose_recommendation_prompt(
            task="t",
            catalog=[],
            memory_hits=None,
            agent_id="scout",
            agent_identity=self._IDENTITY,
        )
        p_without = compose_recommendation_prompt(
            task="t", catalog=[], memory_hits=None, agent_id="scout"
        )
        assert self._IDENTITY not in p_with.system
        assert p_with.system == p_without.system

    def test_agent_identity_determinism_across_calls(self):
        """Byte-equality of both prompts across two identical-input
        calls including `agent_identity` — the determinism contract
        extends to the new param.
        """
        catalog = _sample_catalog()
        kwargs = dict(
            task="analyze this CSV",
            catalog=catalog,
            memory_hits=None,
            cwd="/home/lewie",
            agent_id="scout",
            agent_identity=self._IDENTITY,
        )
        a = compose_recommendation_prompt(**kwargs)
        b = compose_recommendation_prompt(**kwargs)
        assert a.system == b.system
        assert a.user == b.user
