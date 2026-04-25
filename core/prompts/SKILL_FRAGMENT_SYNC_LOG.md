# Skill-fragment sync log (historical)

*This file documented the byte-identity sync between Concierge's
prompt-fragment Python modules and their OpenClaw skill-file
sources during the v3 build period (2026-04-20 through 2026-04-28).
**Retired pre-public-push** per DECISIONS
`[2026-04-29 Day 8] EXTRACT invariant retired pre-public-push`,
when Concierge transitioned from a private extract maintaining
drift-detection against OpenClaw to a standalone public artifact.
Preserved as a historical note for narrative continuity.*

## What this file used to track

Per DECISIONS `[2026-04-21 05:50]`, the prompt-fragment modules in
`core/prompts/*.py` were governed by an **EXTRACT invariant**: each
constant was a byte-for-byte verbatim copy of a section of an
OpenClaw skill source file under `_legacy/`. This sync log carried
per-fragment provenance — source path, SHA-256, mtime, byte count,
section-extraction notes, and a chronological re-sync history — so
that drift between the Concierge-side constant and the OpenClaw
source could be detected and reconciled.

The five Class-1 prompt fragments under that invariant:

- **X3** — `core/prompts/tool_awareness.py` (from
  `_legacy/agent-skills/shared/tool-awareness.md`)
- **X4** — `core/prompts/tool_recommendation.py` (from
  `_legacy/agent-skills/shared/tool-recommendation.md`)
- **X6** — `core/prompts/tool_discovery.py` (from
  `_legacy/openclaw-workspace/skills/tool-discovery/SKILL.md`)
- **X7-A** — `core/prompts/tool_lifecycle.py` (from the
  `## Weekly review` section of
  `_legacy/openclaw-workspace/skills/tool-lifecycle/SKILL.md`)
- **X8** — `core/prompts/soul_delta.py` (from
  `_legacy/openclaw-root/SOUL.md`)

## Why the invariant was retired

The byte-identity sync was load-bearing while Concierge was a
private extract whose value depended on knowing when its prompt
fragments diverged from OpenClaw's skill files. As a public release
artifact, Concierge stands on its own: drift-against-OpenClaw is no
longer a meaningful signal for the public audience, who don't have
the OpenClaw sources to drift against. The invariant's costs
(operator-private workflow content baked into the worked examples,
brand-specific tool IDs, dashboard URLs, anti-bot-circumvention
descriptions) outweighed its benefits at the public-release
boundary.

Per the retirement decision, prompt-fragment constants are now
**Concierge-canonical**: they are the source of truth for the
prompt content; no external sync target exists. Worked examples
were sanitized to generic scenarios (survey-CSV processing,
generic campaign-delivery, generic notification step) while
preserving fleet-narrative names (Alfred, Scout, Dispatch, Radar,
Bridge) and Class-2 operator paths (`~/.satiety-pipeline/`,
`~/.openclaw/logs/`, `~/.agent-skills/shared/TOOL-MANIFEST.md`).

## What replaced this file's role

- **Source of truth for prompt content**: the per-fragment Python
  modules under `core/prompts/`, directly editable.
- **Drift detection**: not applicable. Future edits land in the
  Python module; review goes through normal commit review.
- **Provenance / lineage**: each fragment's docstring records the
  original OpenClaw source path as historical lineage but does not
  claim ongoing byte-identity.
- **Cross-fragment numeric-threshold drift** (the X7 partial-
  hybrid case where prose-thresholds in the prompt fragment must
  align with numeric constants in `core/lifecycle_policy.py`):
  still enforced by
  `tests/test_lifecycle_policy.py`'s source-cross-check, which
  asserts literal threshold phrases stay aligned across the two
  files. That mechanism is independent of the EXTRACT invariant
  and continues to apply.

## Historical context

The Class-1 invariant served the v3 build period well: it caught
multiple drift events between Concierge and OpenClaw across Days
2-7, each of which forced a deliberate joint-review of both sides
before either changed. The pattern (verbose constant naming with
`__FROM_{SOURCE}_*` suffixes for grep-drift visibility, byte-for-
byte source comparison, mandatory sync-log entries on re-paste)
is preserved in the constant names themselves — those naming
conventions remain in place as historical artifacts of the
build-period discipline. Future contributors looking at
`TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD` may find the
suffix unusual; this file documents why.

The retirement was not a repudiation of the discipline. It was
the recognition that a discipline appropriate for the build period
(when synced-against-private-source mattered) is wrong-shaped for
the release boundary (where the artifact stands on its own).

See `planning/decisions/DECISIONS.md` entry
`[2026-04-29 Day 8] EXTRACT invariant retired pre-public-push`
for the formal retirement record.
