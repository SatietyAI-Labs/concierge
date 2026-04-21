"""Prompt fragments composed into POST /recommend's Opus 4.7 system prompt.

Each fragment lives in its own module with a full provenance header
(source path, sha256, mtime, extract timestamp, section extracted,
OpenClaw coupling notes). Per-fragment separation is intentional per
the Option B decision made in SESSION-2026-04-21-02: 1:1 source-file
to Python-file mapping gives git-log --follow, file-mtime-as-sync-date,
and per-fragment remediation a natural surface.

Sync status across all fragments is tracked in
`SKILL_FRAGMENT_SYNC_LOG.md` alongside this file.

Governing decision: DECISIONS [2026-04-21 05:50] — EXTRACT as prompt
fragments with structural mitigations #1-4. Phase 2 deferred target:
build-time regeneration via `make sync-prompts`.
"""

from core.prompts.tool_awareness import (
    TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD,
)
from core.prompts.tool_discovery import (
    TOOL_DISCOVERY_PROTOCOL__FROM_TOOL_DISCOVERY_SKILL,
)
from core.prompts.tool_recommendation import (
    TOOL_RECOMMENDATION_PROTOCOL__FROM_TOOL_RECOMMENDATION_MD,
)

__all__ = [
    "TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD",
    "TOOL_DISCOVERY_PROTOCOL__FROM_TOOL_DISCOVERY_SKILL",
    "TOOL_RECOMMENDATION_PROTOCOL__FROM_TOOL_RECOMMENDATION_MD",
]
