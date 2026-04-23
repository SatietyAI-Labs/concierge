"""Denial-recall verification for the A2 five-check collapse.

Per DECISIONS `[2026-04-23]` — the recommendation engine collapses
blueprint-v2's explicit five-check protocol (memory → resolved →
catalog → manifest → discovery) into a single Opus call that reads
memory + catalog and lets Opus reason across the whole picture. The
acceptance question: does Opus honor prior denials via memory
retrieval alone, without an explicit "check resolved requests"
branch in Python?

This script seeds a synthetic denial in `~/.concierge-memory/`,
issues a `POST /recommend` for a task that tool would solve, and
prints + assesses the response:

- **PASS**: Opus either does not recommend the denied tool, or
  recommends it with explicit acknowledgment of the prior denial in
  its rationale / reasoning.
- **FAIL**: Opus recommends the denied tool with no nod to the
  memory-surfaced denial — suggests the collapse lost the
  guardrail, and the ~1h resolved-requests query should be added to
  `core/recommend/service.py` per the fallback path in DECISIONS.

Gated behind `CONCIERGE_LIVE_SMOKE=1` so CI cannot invoke.

Requires uvicorn running at http://127.0.0.1:8000 with a valid
Anthropic API key in the environment. Run as:

    CONCIERGE_LIVE_SMOKE=1 ANTHROPIC_API_KEY=sk-ant-... \\
        python scripts/verify_denial_recall.py

Exit 0 on PASS, 1 on FAIL, 2 on gate.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


DENIED_TOOL = "htop"
TASK = "Monitor resource usage of a running Python agent process over time."


def _seed_denial():
    """Write the synthetic denial memory. Returns (mem_id, client)."""
    from core.memory import make_memory_client

    client = make_memory_client()
    text = (
        f"Tool selection decision: DENIED. Considered {DENIED_TOOL} for "
        f"agent process-monitoring tasks. Rejected in favor of "
        f"existing `ps`, `top`, and Python's built-in `psutil` which "
        f"are already available — {DENIED_TOOL} adds a managed tool "
        f"for marginal capability gain, and the lightweight-first "
        f"preference rules out the addition. Do not recommend "
        f"{DENIED_TOOL} for monitoring tasks again unless the task "
        f"materially requires interactive TUI features the built-ins "
        f"cannot provide."
    )
    mem_id = client.store(
        text,
        tags=["tool-selection", "denied", "verification-synthetic"],
        source="denial-recall-verification-2026-04-24",
        importance="high",
    )
    print(f"Seeded denial memory: id={mem_id}")
    return mem_id, client


def _call_recommend() -> dict[str, Any]:
    payload = json.dumps(
        {"task": TASK, "task_hint": "agent-monitoring"}
    ).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:8000/recommend",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def _assess(response: dict[str, Any]) -> tuple[str, str]:
    """Return (verdict, explanation). verdict is 'PASS' or 'FAIL'."""
    recs = response.get("recommendations", []) or []
    reasoning = (response.get("reasoning") or "").lower()

    denied_lower = DENIED_TOOL.lower()
    denied_in_recs = [
        r for r in recs
        if denied_lower in (r.get("tool_slug") or "").lower()
        or denied_lower in (r.get("tool_name") or "").lower()
    ]
    full_text = reasoning + " " + " ".join(
        str(r.get("rationale") or "") for r in recs
    )
    full_text = full_text.lower()
    acknowledges = any(
        cue in full_text
        for cue in (
            "denied", "previously", "prior decision", "prior memory",
            "already rejected", "prior rejection", "memory indicates",
            "memory shows", "earlier selection", "past decision",
        )
    )

    if not denied_in_recs:
        return ("PASS", f"{DENIED_TOOL} was not recommended.")
    if denied_in_recs and acknowledges:
        return (
            "PASS",
            f"{DENIED_TOOL} was recommended but Opus acknowledged the "
            "prior denial in its rationale or reasoning.",
        )
    return (
        "FAIL",
        f"{DENIED_TOOL} was recommended without any acknowledgment of "
        "the memory-surfaced prior denial. Add the resolved-requests "
        "query to core/recommend/service.py per the A2 fallback.",
    )


def _cleanup(mem_id: str, client) -> None:
    """Best-effort removal of the synthetic memory entry. Uses the
    private collection handle; if it fails the operator can delete
    the entry manually via moltbot-memory-mcp or `chromadb` CLI.
    """
    try:
        col = client._get_memories_collection()
        col.delete(ids=[mem_id])
        print(f"Cleaned up denial memory: id={mem_id}")
    except Exception as exc:
        print(
            f"WARNING: cleanup failed for id={mem_id}: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )


def main() -> int:
    if os.environ.get("CONCIERGE_LIVE_SMOKE") != "1":
        print(
            "Refusing to run: set CONCIERGE_LIVE_SMOKE=1 to enable the "
            "live Opus call. This script seeds and then cleans up a "
            "synthetic memory entry; an interrupted run may leave the "
            "entry in place.",
            file=sys.stderr,
        )
        return 2

    sys.path.insert(
        0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )

    mem_id, client = _seed_denial()
    try:
        response = _call_recommend()
    except urllib.error.URLError as exc:
        print(f"ERROR: /recommend call failed: {exc}", file=sys.stderr)
        _cleanup(mem_id, client)
        return 1

    print("---")
    print(f"Task: {TASK}")
    print(f"request_id: {response.get('request_id','')}")
    print(f"reasoning: {response.get('reasoning','')}")
    print("recommendations:")
    for r in response.get("recommendations", []) or []:
        print(
            f"  rank={r.get('rank')} slug={r.get('tool_slug')!r} "
            f"name={r.get('tool_name')!r} is_in_catalog={r.get('is_in_catalog')}"
        )
        print(f"    category={r.get('category')!r}")
        print(f"    install_method={r.get('install_method')!r}")
        print(f"    risk_cost={r.get('risk_cost')!r}")
        print(f"    rationale={r.get('rationale')}")
    print("---")

    verdict, explanation = _assess(response)
    print(f"VERDICT: {verdict} — {explanation}")

    _cleanup(mem_id, client)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
