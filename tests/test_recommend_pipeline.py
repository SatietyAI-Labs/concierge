"""N14 — CI-safe regression guard for the recommendation pipeline.

## Purpose

Guard the **composition layer** that sits above every existing test slice:
`RecommendationService.recommend()` → `build_gap_report(...)` →
`render_recommend_result(...)` → final markdown the Claude Code user
reads during soak.

No existing CI-safe test exercises this full composition end-to-end
with fixture-realistic inputs. The moneyshot baseline in DECISIONS
[2026-04-22 16:27] verified it against reality, but that verification
is not machine-checkable — `tests/test_smoke_live_anthropic.py` runs
against real Opus (live_smoke-gated, no CI coverage).

This file's role: given fixture-realistic inputs and a `FakeAnthropic`
returning a moneyshot-shaped response, assert the rendered markdown
has the structural invariants the soak operator will read. If a
refactor silently re-orders the pinned markdown, or a render helper
loses the preamble-informed "do not block" wording, or a parse-layer
field rename breaks gap-report dict access, this test catches it
before a soak session does.

## What this file does NOT do (scope guard)

- Does NOT re-assert request-shape invariants (temperature-absent,
  output_config-present) — those are pinned in
  `tests/test_recommend_client.py::TestOutgoingRequestShape`.
- Does NOT re-assert protocolVersion or cold-start timeout constants
  — those are pinned in `tests/test_shim_e2e.py`.
- Does NOT re-assert gap-report firing rules on hand-crafted dicts —
  those are pinned in `tests/test_meta_tools_gap_report.py` (19
  tests). N14 tests the same rules in their *composed* context, with
  realistic catalog + task + parsed response flowing through.

The per-component tests stay the low-level tripwires; N14 is one
layer above them. If a scenario here breaks but every component test
stays green, the drift is in composition — exactly the gap the
moneyshot baseline revealed and Tier 1 drift detection closes.

## Relationship to Tier 1 drift detection

The three FakeAnthropic content constants below are also the
specification that `core.recommend.validator.validate_response_shape`
enforces against real Opus responses. Per the N14 Tier-1 addition:
the fixture-driven tests define what a valid response shape looks
like; `validate_response_shape` runs those same structural checks
against actual responses in production, logging
`recommend.fixture_drift_detected` when the real API evolves past the
fixtures. That turns the fixture corpus from "remember to update"
into "self-detecting drift."
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from adapters.claude_code.meta_tools.gap_report import build_gap_report
from adapters.claude_code.meta_tools.render import render_recommend_result
from core.memory import MemoryHit
from core.recommend.client import AnthropicCall
from core.recommend.counters import RecommendCounters
from core.recommend.prompt import CatalogToolView
from core.recommend.schemas import RecommendRequest
from core.recommend.service import RecommendationService


FIXTURES = Path(__file__).resolve().parent.parent / "planning" / "test-fixtures"


# ---- FakeAnthropic content constants modeled on the moneyshot --------------
# Shapes mirror what real Opus 4.7 returned in the 2026-04-22 16:27
# baseline run (request_id=33b0ae69-e1a). Kept as module constants so
# drift between this specification and real responses is a git-blame
# away — and so `validate_response_shape` can use these same three
# shapes as the ground-truth spec.

MONEYSHOT_DISCOVERY_CONTENT = json.dumps(
    {
        "reasoning": (
            "For CSV column-level statistics with quoted-field and "
            "UTF-8 handling, prefer a lightweight CLI over a "
            "heavyweight library. csvstat from the csvkit pack is the "
            "direct fit. miller is not currently in the catalog but is "
            "the strongest discovery alternative for the top-N-by-column "
            "half of the task."
        ),
        "recommendations": [
            {
                "rank": 1,
                "tool_slug": "csvstat",
                "tool_name": "csvstat",
                "rationale": (
                    "Per-column min/max/mean/null counts over a CSV; "
                    "handles quoted fields and UTF-8 correctly. "
                    "Lightweight CLI, matches the task shape exactly."
                ),
                "confidence": "high",
                "is_in_catalog": True,
            },
            {
                "rank": 2,
                "tool_slug": None,
                "tool_name": "miller",
                "rationale": (
                    "Streaming CSV processor; `mlr top -n 5 -f open_rate` "
                    "handles the top-N-by-column portion in one call. "
                    "Lightweight CLI but not in current catalog."
                ),
                "confidence": "medium",
                "is_in_catalog": False,
            },
        ],
    }
)


CLEAN_HAPPY_CONTENT = json.dumps(
    {
        "reasoning": (
            "csvstat is the direct fit for this task — a lightweight "
            "CLI handling exactly the column-stats shape requested. "
            "No discovery alternative is needed."
        ),
        "recommendations": [
            {
                "rank": 1,
                "tool_slug": "csvstat",
                "tool_name": "csvstat",
                "rationale": (
                    "Per-column min/max/mean/null counts over a CSV. "
                    "Lightweight CLI, in-catalog, task-shape match."
                ),
                "confidence": "high",
                "is_in_catalog": True,
            }
        ],
    }
)


EMPTY_RECS_CONTENT = json.dumps(
    {
        "reasoning": (
            "Task description is ambiguous — no ranked recommendation "
            "would honestly serve the caller. Suggest rephrasing or "
            "browsing the catalog directly."
        ),
        "recommendations": [],
    }
)


# ---- Fixture loading -------------------------------------------------------


def _load_catalog() -> list[CatalogToolView]:
    """Load `planning/test-fixtures/sample-catalog-state.json` as
    `CatalogToolView` list. Mirrors the mapping used by
    `tests/test_smoke_live_anthropic.py` so the same fixture drives
    both the CI-safe guard and the live-smoke baseline.
    """
    state = json.loads(
        (FIXTURES / "sample-catalog-state.json").read_text(encoding="utf-8")
    )
    return [
        CatalogToolView(
            slug=t["slug"],
            name=t["name"],
            description=t.get("description"),
            category=t.get("category"),
            pack_slug=t.get("pack_slug"),
            is_in_manifest=t["is_in_manifest"],
            is_active=t["is_active"],
        )
        for t in state["tools"]
    ]


def _load_task_text() -> str:
    return (FIXTURES / "sample-task.md").read_text(encoding="utf-8")


# ---- Test doubles ----------------------------------------------------------


@dataclass
class FakeMemory:
    """Memory stand-in — returns a fixed hit list, no ChromaDB."""

    hits: list[MemoryHit] = field(default_factory=list)
    identity: str = ""

    def search(self, query: str, *, limit: int = 5) -> list[MemoryHit]:
        return list(self.hits)

    def identity_get(self, *, key: str = "default") -> str:
        return self.identity


@dataclass
class FakeAnthropic:
    """Captures the prompts passed in and returns the curated content.
    Mirrors the shape `service.recommend()` reads from the real
    `AnthropicRecommender`.
    """

    content: str = ""
    last_system: Optional[str] = None
    last_user: Optional[str] = None
    effort: str = "xhigh"

    def call(self, *, system: str, user: str) -> AnthropicCall:
        self.last_system = system
        self.last_user = user
        return AnthropicCall(
            content=self.content,
            stop_reason="end_turn",
            tokens_in=1200,
            tokens_out=280,
            model_echo="claude-opus-4-7",
            latency_ms=8500,
        )


def _run_pipeline(
    *,
    anthropic_content: str,
    memory_hits: Optional[list[MemoryHit]] = None,
) -> tuple[FakeAnthropic, str]:
    """Drive the full composition pipeline for one fixture scenario.

    Returns the FakeAnthropic (so tests can inspect the composed
    prompt) and the final rendered markdown that a Claude Code
    operator would read as the `concierge_recommend` result.
    """
    anthropic = FakeAnthropic(content=anthropic_content)
    memory = FakeMemory(hits=memory_hits or [])
    catalog = _load_catalog()
    service = RecommendationService(
        memory=memory,  # type: ignore[arg-type]
        anthropic=anthropic,  # type: ignore[arg-type]
        fetch_catalog=lambda: catalog,
        memory_search_limit=5,
        counters=RecommendCounters(),
    )

    response = service.recommend(
        RecommendRequest(
            task=_load_task_text(),
            cwd="/home/lewie/work/subscribers-analysis",
            task_hint="data-analysis",
            active_tools=None,
        )
    )

    response_dict = response.model_dump()
    gap_markdown = build_gap_report(response_dict)
    rendered = render_recommend_result(
        response_dict, gap_report_markdown=gap_markdown
    )
    return anthropic, rendered


def _moneyshot_memory_hits() -> list[MemoryHit]:
    """Memory-healthy fixture state for the clean-happy scenario. One
    prior decision for a similar task pattern — the minimal block
    requires memory_hit_count > 0 AND memory_available=True.
    """
    return [
        MemoryHit(
            id="mem_csv_prior",
            text="Prior CSV analysis task resolved to csvstat from csvkit pack.",
            similarity=0.88,
            tags=("tool-selection",),
            importance="normal",
            source="test-fixture",
            created_at="2026-04-20T12:00:00",
        )
    ]


# ---- Scenario tests --------------------------------------------------------


class TestFixtureDrivenPipeline:
    """Three scenarios stitched end-to-end with fixture inputs and
    curated FakeAnthropic content modeled on the moneyshot baseline.
    """

    def test_discovery_scenario_renders_full_gap_report(self):
        """Moneyshot shape: csvstat in-catalog high + miller discovery
        medium. Every gap-report sub-section should fire, the SNA
        should render the discovery-route variant with do-not-block
        wording, and the final markdown should have the full pinned
        grammar (Top-ranked → Gap report → Summary).
        """
        _, rendered = _run_pipeline(
            anthropic_content=MONEYSHOT_DISCOVERY_CONTENT,
            memory_hits=_moneyshot_memory_hits(),
        )

        # Pinned-grammar sections present in order
        assert "## Recommendations" in rendered
        assert rendered.index("### Top-ranked") < rendered.index("### Gap report")
        assert rendered.index("### Gap report") < rendered.index("### Summary")

        # Top-ranked block names both tools with their correct labels
        top_block = rendered[
            rendered.index("### Top-ranked"): rendered.index("### Gap report")
        ]
        assert "csvstat" in top_block
        assert "miller" in top_block
        assert "catalog: yes" in top_block  # csvstat in-catalog label
        assert "catalog: discovery" in top_block  # miller discovery label

        # Gap-report: Not-in-catalog + Memory coverage + SNA all fire.
        # (Low-confidence sub-section does NOT fire here — neither rec
        # is low-confidence. That asymmetry is itself the signal.)
        gap_block = rendered[
            rendered.index("### Gap report"): rendered.index("### Summary")
        ]
        assert "#### Not in catalog (1 tool)" in gap_block
        assert "miller" in gap_block  # named in discovery sub-section
        assert "#### Low-confidence matches" not in gap_block
        assert "#### Memory coverage" in gap_block
        assert "#### Suggested next action" in gap_block

        # SNA discovery-route variant: do-not-block phrasing informed by
        # CLAUDE_CODE_GAP_PREAMBLE. Guards against a rewording that
        # silently loses the behavioral voice.
        assert "concierge_request_tool" in gap_block
        assert "do not block" in gap_block.lower()

    def test_clean_happy_path_renders_minimal_gap_block(self):
        """No discoveries, no low-confidence, memory hits present,
        all recs in-catalog + high. Gap report collapses to the
        pinned one-liner sentinel; no sub-section headings appear.
        """
        _, rendered = _run_pipeline(
            anthropic_content=CLEAN_HAPPY_CONTENT,
            memory_hits=_moneyshot_memory_hits(),
        )

        # Pinned grammar still holds
        assert "### Top-ranked" in rendered
        assert "### Gap report" in rendered
        assert "### Summary" in rendered

        gap_block = rendered[
            rendered.index("### Gap report"): rendered.index("### Summary")
        ]
        # Minimal-block sentinel present; no sub-section headings fire.
        assert "No gaps detected" in gap_block
        assert "#### Not in catalog" not in gap_block
        assert "#### Low-confidence matches" not in gap_block
        assert "#### Memory coverage" not in gap_block
        assert "#### Suggested next action" not in gap_block

    def test_empty_recommendations_renders_rephrase_catchall(self):
        """Valid JSON, `recommendations: []`. Gap report fires because
        empty-recs is itself a gap signal (per N12 commit `b31c32a`
        bugfix). Memory-coverage sub-section MUST NOT fire — empty
        recs means no ranking to inform. SNA should render the
        rephrase-or-browse catch-all.
        """
        _, rendered = _run_pipeline(
            anthropic_content=EMPTY_RECS_CONTENT,
            memory_hits=_moneyshot_memory_hits(),
        )

        gap_block = rendered[
            rendered.index("### Gap report"): rendered.index("### Summary")
        ]
        # Gap report present but the pinned grammar below is non-minimal
        # because empty-recs triggers a gap signal.
        assert "No gaps detected" not in gap_block

        # Memory coverage NOT rendered — no recs to assess.
        assert "#### Memory coverage" not in gap_block

        # SNA catch-all language names concierge_list_active + rephrase.
        assert "#### Suggested next action" in gap_block
        assert "rephras" in gap_block.lower()  # "rephrase" or "rephrasing"
        assert "concierge_list_active" in gap_block

    def test_pipeline_plumbing_carries_fixture_inputs_to_prompt(self):
        """Sanity: the fixture catalog + fixture task text flow
        through `compose_recommendation_prompt` intact. Guards against
        a CatalogToolView mapping regression (e.g. a field rename
        that silently drops `pack_slug` from the user message) or a
        task-text loader mutation.
        """
        fake_anthropic, _ = _run_pipeline(
            anthropic_content=CLEAN_HAPPY_CONTENT,
            memory_hits=_moneyshot_memory_hits(),
        )

        # Task text — the canonical fixture mentions "open_rate" and
        # "UTF-8 emoji" verbatim.
        assert fake_anthropic.last_user is not None
        assert "open_rate" in fake_anthropic.last_user
        assert "UTF-8" in fake_anthropic.last_user

        # Catalog — every fixture slug should appear in the user
        # message's "Available tools" section. `csvlook` is dormant
        # in the fixture; rendering still includes it with the
        # dormant tag (the prompt composer surfaces all catalog
        # entries regardless of active state).
        for slug in ("csvstat", "csvsort", "csvgrep", "csvlook", "pandas"):
            assert slug in fake_anthropic.last_user, (
                f"fixture slug {slug!r} did not reach the composed prompt"
            )

        # Context lines — cwd + task_hint reach the prompt.
        assert "/home/lewie/work/subscribers-analysis" in fake_anthropic.last_user
        assert "data-analysis" in fake_anthropic.last_user
