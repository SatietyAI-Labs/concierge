"""N8 — fixture-driven recommendation assertion against real Anthropic.

**Risk #1 mitigation** per Phase E gap-analysis §E.2.1 + build-plan
§F.2.2 N8 row. Runs the canonical `sample-task.md` through a real
Opus 4.7 call with the `sample-catalog-state.json` catalog and
asserts the lightweight-first preference holds: any csvkit-family
tool ranks above `pandas`.

**Gated.** This test is marked `@pytest.mark.live_smoke` and will
only collect under `pytest -m live_smoke`. Even when collected, it
skips gracefully if no Anthropic API key is resolvable from either
`CONCIERGE_ANTHROPIC_API_KEY` or `ANTHROPIC_API_KEY`.

**Baseline, not regression guard.** If this assertion fails during
soak, the correct response is to read `planning/test-fixtures/
expected-recommendation.md` §"Drift interpretation" and bisect
between reality-shift, regression, and catalog-state drift — NOT
to immediately retune the prompt.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


FIXTURES = Path(__file__).resolve().parent.parent / "planning" / "test-fixtures"

CSVKIT_FAMILY = {"csvstat", "csvsort", "csvgrep", "csvlook", "csvkit"}


def _resolve_api_key() -> str | None:
    return os.environ.get("CONCIERGE_ANTHROPIC_API_KEY") or os.environ.get(
        "ANTHROPIC_API_KEY"
    )


@pytest.mark.live_smoke
def test_live_anthropic_recommendation_prefers_csvkit_over_pandas():
    """Canonical assertion: for the sample-task (CSV analysis),
    a csvkit-family tool ranks above pandas.
    """
    api_key = _resolve_api_key()
    if not api_key:
        pytest.skip(
            "no Anthropic API key in CONCIERGE_ANTHROPIC_API_KEY or "
            "ANTHROPIC_API_KEY; live_smoke requires one"
        )

    from core.memory import MemoryHit
    from core.recommend.client import AnthropicRecommender
    from core.recommend.prompt import CatalogToolView
    from core.recommend.schemas import RecommendRequest
    from core.recommend.service import RecommendationService

    catalog_state = json.loads(
        (FIXTURES / "sample-catalog-state.json").read_text(encoding="utf-8")
    )
    catalog: list[CatalogToolView] = [
        CatalogToolView(
            slug=t["slug"],
            name=t["name"],
            description=t.get("description"),
            category=t.get("category"),
            pack_slug=t.get("pack_slug"),
            is_in_manifest=t["is_in_manifest"],
            is_active=t["is_active"],
        )
        for t in catalog_state["tools"]
    ]

    # Stub memory returns the operator-preference hint the skill
    # protocols reference — deterministic under the pinned model,
    # avoids hitting a real ChromaDB.
    class _StaticMemory:
        def search(self, query, *, limit=5):
            return [
                MemoryHit(
                    id="mem_smoke_live",
                    text=(
                        "Operator prefers lightweight CLI tools over heavy "
                        "libraries when both serve a task."
                    ),
                    similarity=0.91,
                    tags=("tool-selection", "preference"),
                    importance="normal",
                    source="smoke-fixture",
                    created_at="2026-04-20T12:00:00",
                )
            ]

    anthropic = AnthropicRecommender(
        api_key=api_key,
        model="claude-opus-4-7",
        temperature=0.0,
        max_tokens=2048,
    )
    service = RecommendationService(
        memory=_StaticMemory(),  # type: ignore[arg-type]
        anthropic=anthropic,
        fetch_catalog=lambda: catalog,
        memory_search_limit=5,
    )

    # Read the task text from the canonical fixture. Mirrors what
    # Claude Code would send via `concierge_recommend`.
    task_md = (FIXTURES / "sample-task.md").read_text(encoding="utf-8")

    response = service.recommend(
        RecommendRequest(
            task=task_md,
            cwd="/home/lewie/work/subscribers-analysis",
            task_hint="data-analysis",
            active_tools=None,
        )
    )

    assert response.model == "claude-opus-4-7"
    assert response.temperature == 0.0
    assert len(response.recommendations) >= 1, (
        "Opus returned zero recommendations for the canonical CSV task"
    )

    # Collect ranks for csvkit-family tools and pandas.
    ranks_by_slug = {
        (r.tool_slug or r.tool_name.lower()): r.rank
        for r in response.recommendations
    }

    csvkit_ranks = [
        rank for slug, rank in ranks_by_slug.items() if slug in CSVKIT_FAMILY
    ]
    pandas_rank = ranks_by_slug.get("pandas")

    # Primary assertion per expected-recommendation.md:
    # - If pandas is absent, lightweight-first is fully honored.
    # - Otherwise, at least one csvkit-family rank must be strictly
    #   less than pandas.
    if pandas_rank is None:
        assert csvkit_ranks, (
            "neither pandas nor any csvkit-family tool was recommended — "
            "Opus declined the catalog entirely"
        )
    else:
        assert csvkit_ranks, (
            "pandas was recommended but no csvkit-family tool was — "
            "lightweight-first preference inverted"
        )
        assert min(csvkit_ranks) < pandas_rank, (
            f"csvkit-family rank {min(csvkit_ranks)} did not beat pandas "
            f"rank {pandas_rank}; lightweight-first preference inverted"
        )

    # Log the observations the soak operator uses to distinguish
    # drift modes. Available in `pytest -s` output.
    print(
        f"\n[soak-baseline] model={response.model} "
        f"tokens_in={response.token_usage.input} "
        f"tokens_out={response.token_usage.output} "
        f"rec_count={len(response.recommendations)} "
        f"csvkit_ranks={sorted(csvkit_ranks)} "
        f"pandas_rank={pandas_rank} "
        f"stop_reason={response.stop_reason}"
    )
