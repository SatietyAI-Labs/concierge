"""Live N6 smoke against real Anthropic.

Runs ONE Opus 4.7 call with the composed recommendation prompt and
prints the full observable surface: system-prompt hash+length,
user-message hash+length, response stop_reason, tokens, latency,
and the parsed recommendations.

Gated behind `CONCIERGE_LIVE_SMOKE=1` so CI can never invoke. Run
as:

    CONCIERGE_LIVE_SMOKE=1 CONCIERGE_ANTHROPIC_API_KEY=sk-ant-... \\
        python scripts/recommend_live_smoke.py

or with the SDK's default env var:

    CONCIERGE_LIVE_SMOKE=1 ANTHROPIC_API_KEY=sk-ant-... \\
        python scripts/recommend_live_smoke.py

Exit code 0 on success, non-zero on any failure. Do not commit an
API key to the repo.
"""
from __future__ import annotations

import logging
import os
import sys


def main() -> int:
    if os.environ.get("CONCIERGE_LIVE_SMOKE") != "1":
        print(
            "Refusing to run: set CONCIERGE_LIVE_SMOKE=1 to enable live "
            "Anthropic calls. This gate prevents accidental API use "
            "during CI or dev loops.",
            file=sys.stderr,
        )
        return 2

    # Path is repo-relative; allow running without installing the
    # package.
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Emit all recommend-engine logs to stdout at DEBUG so the
    # operator can see exactly what the 48h soak log surface
    # will look like on the real flow.
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    from core.config import get_settings
    from core.memory import MemoryHit
    from core.recommend.client import AnthropicRecommender
    from core.recommend.counters import RecommendCounters
    from core.recommend.prompt import CatalogToolView
    from core.recommend.schemas import RecommendRequest
    from core.recommend.service import RecommendationService

    settings = get_settings()
    api_key = (
        settings.anthropic_api_key.get_secret_value()
        if settings.anthropic_api_key
        else None
    )

    anthropic = AnthropicRecommender(
        api_key=api_key,
        model=settings.anthropic_model,
        temperature=settings.recommend_temperature,
        max_tokens=settings.recommend_max_tokens,
    )

    # Sample catalog that mirrors fixture state the 48h soak will
    # see: a lightweight CLI, a heavier library, a dormant entry,
    # and a pending entry so the state-annotation surface is
    # exercised.
    catalog = [
        CatalogToolView(
            slug="csvstat",
            name="csvstat",
            description="Summary statistics for CSV files; part of csvkit.",
            category="data",
            pack_slug="csvkit",
            is_in_manifest=True,
            is_active=True,
        ),
        CatalogToolView(
            slug="pandas",
            name="pandas",
            description="Data analysis library for Python.",
            category="data",
            pack_slug=None,
            is_in_manifest=True,
            is_active=False,  # dormant
        ),
        CatalogToolView(
            slug="duckdb",
            name="DuckDB",
            description="In-process analytical SQL database.",
            category="data",
            pack_slug=None,
            is_in_manifest=False,
            is_active=True,  # pending
        ),
    ]

    class _StaticMemory:
        def search(self, query: str, *, limit: int = 5):
            return [
                MemoryHit(
                    id="mem_smoke_01",
                    text="Lewie prefers lightweight CLI tools over heavy libraries when both work.",
                    similarity=0.91,
                    tags=("tool-selection", "preference"),
                    importance="normal",
                    source="smoke-fixture",
                    created_at="2026-04-20T12:00:00",
                )
            ]

    svc = RecommendationService(
        memory=_StaticMemory(),  # type: ignore[arg-type]
        anthropic=anthropic,
        fetch_catalog=lambda: catalog,
        memory_search_limit=settings.recommend_memory_search_limit,
        counters=RecommendCounters(),
    )

    req = RecommendRequest(
        task="analyze this 2GB CSV of sales transactions quickly",
        cwd="/home/lewie/work/sales-analysis",
        task_hint="data-analysis",
        active_tools=["pandas"],
    )

    try:
        resp = svc.recommend(req)
    except Exception as exc:
        print(f"\n*** LIVE SMOKE FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print("\n=== LIVE SMOKE RESULT ===")
    print(f"request_id: {resp.request_id}")
    print(f"model: {resp.model}")
    print(f"temperature: {resp.temperature}")
    print(f"stop_reason: {resp.stop_reason}")
    print(f"memory_available: {resp.memory_available}")
    print(f"memory_hit_count: {resp.memory_hit_count}")
    print(
        f"latency_ms: total={resp.latency_ms.total} memory={resp.latency_ms.memory} "
        f"model={resp.latency_ms.model} parse={resp.latency_ms.parse}"
    )
    print(
        f"token_usage: input={resp.token_usage.input} output={resp.token_usage.output} "
        f"total={resp.token_usage.total}"
    )
    print(f"reasoning: {resp.reasoning}")
    print(f"recommendations ({len(resp.recommendations)}):")
    for r in resp.recommendations:
        print(
            f"  #{r.rank} {r.tool_name} "
            f"(slug={r.tool_slug}, confidence={r.confidence}, "
            f"in_catalog={r.is_in_catalog})"
        )
        print(f"    rationale: {r.rationale}")
    print("=== END ===\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
