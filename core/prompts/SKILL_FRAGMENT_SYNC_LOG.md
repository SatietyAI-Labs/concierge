# Skill-Fragment Sync Log

Governing decision: **DECISIONS `[2026-04-21 05:50]`** — *Skill-extraction
pattern: EXTRACT as prompt fragments (not pure Python, not ADAPT).*
This file implements structural mitigation #2 from that entry.

## What this file tracks

Each row under §Current fragments records the provenance of a Python
string constant in `core/prompts/*.py` against the skill-file source
it was extracted from. Each entry under §Sync history is an append-only
record of every extract / re-extract event.

Purpose: make source-of-truth drift between OpenClaw-side skill files
(under `_legacy/agent-skills/`) and Concierge-side prompt fragments
visible to a reader of this log alone, without requiring them to
diff file contents.

## Drift model (hackathon week)

**Manual re-paste**, per DECISIONS `[2026-04-21 05:50]` mitigation #4.

When a source skill file changes:
1. Re-read the source body.
2. Re-paste verbatim into the corresponding constant in
   `core/prompts/<fragment>.py`.
3. Update the Source SHA-256 / mtime / bytes lines in that module's
   header comment block.
4. Update the fragment's row under §Current fragments (new sha, new
   mtime, new extract timestamp).
5. Append a new entry under §Sync history describing the change.
6. Re-run `pytest tests/test_prompts.py` to confirm signal-phrase
   assertions still hold.

## Phase 2 deferred target

Build-time regeneration via `make sync-prompts`. The generator would
read YAML front-matter or HTML-comment markers in the source skill
file to determine extraction boundaries, then regenerate each
`core/prompts/<fragment>.py` module (constant body + header metadata
lines) on demand. This eliminates the manual re-paste step and the
drift risk entirely. Named and deferred per DECISIONS `[2026-04-21
05:50]` §"Phase 2 structural improvement path."

---

## Current fragments

| # | Constant | Module | Source (repo-relative) | Source SHA-256 (first 8) | Source mtime | Source bytes | Extracted |
|---|---|---|---|---|---|---|---|
| X3 | `TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD` | `core/prompts/tool_awareness.py` | `_legacy/agent-skills/shared/tool-awareness.md` | `7d1d2f04` | 2026-03-24 11:21 PDT | 9619 | 2026-04-21 15:43 PDT (SESSION-2026-04-21-02) |
| X4 | `TOOL_RECOMMENDATION_PROTOCOL__FROM_TOOL_RECOMMENDATION_MD` | `core/prompts/tool_recommendation.py` | `_legacy/agent-skills/shared/tool-recommendation.md` | `a014fe22` | 2026-04-13 18:03 PDT | 9571 | 2026-04-21 16:14 PDT (SESSION-2026-04-21-02) |

---

## Sync history

### `2026-04-21 15:43 PDT` — X3 initial extract

- **Constant:** `TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD`
- **Module:** `core/prompts/tool_awareness.py`
- **Source:** `_legacy/agent-skills/shared/tool-awareness.md`
- **Source SHA-256:**
  `7d1d2f040c727d9514806516929be625cde15cc28e134ea3489cd4991d933b6e`
- **Source mtime:** `2026-03-24 11:21:31 -0700`
- **Source bytes:** `9619`
- **Section extracted:** full document body below the YAML
  frontmatter (source lines 6-193). The Anthropic skill-runtime
  metadata (`name:` / `description:` fields on lines 1-4) is
  intentionally excluded — it is skill-loader metadata, not prompt
  content.
- **Fidelity:** VERBATIM. No paraphrase, no reflow, no normalization.
- **OpenClaw coupling preserved:** fleet names (Alfred/Scout/Dispatch/
  Radar/Bridge), pipeline paths under `~/.satiety-pipeline/` and
  `~/.openclaw/`, MailerLite `ml_*` tool IDs, ElevenLabs TTS references,
  port `18789`, and all worked examples. Consumer (N6 `POST /recommend`
  compose step) is responsible for any adapter-specific substitution
  or for trusting Opus 4.7 to generalize.
- **Session:** `SESSION-2026-04-21-02` (Day 1 afternoon session, after
  Day 1 morning arc closed at 10:57 PDT and a food+nap break).
- **Extractor:** Claude Code Opus 4.7 (`claude-opus-4-7[1m]`).
- **Pattern-establishing note:** this is the first fragment extracted
  under the DECISIONS `[2026-04-21 05:50]` protocol; its shape (module
  layout, header-comment structure, constant naming, sync-log row
  format) is the template to reuse for X4, X6, X7, X8.
- **Verify with:** `pytest tests/test_prompts.py::TestToolAwarenessFragment`

### `2026-04-21 16:14 PDT` — X4 initial extract

- **Constant:** `TOOL_RECOMMENDATION_PROTOCOL__FROM_TOOL_RECOMMENDATION_MD`
- **Module:** `core/prompts/tool_recommendation.py`
- **Source:** `_legacy/agent-skills/shared/tool-recommendation.md`
- **Source SHA-256:**
  `a014fe22c892ff30f22b9284f873bf877398903c285c62b56dcfd5637f5d8229`
- **Source mtime:** `2026-04-13 18:03:49 -0700`
- **Source bytes:** `9571`
- **Section extracted:** full document body below the YAML frontmatter
  (source lines 6-143). YAML `name:` / `description:` fields excluded
  (skill-loader metadata, not prompt content).
- **Fidelity:** VERBATIM. One escape applied at the Python-string layer
  only: source byte at offset 5703 is a literal backslash inside the
  worked `find` command (`-printf '%s %p\n'`). The Python constant
  escapes this as `\\n` so the in-memory string value retains the
  literal `\n` byte sequence that appears in the source markdown. The
  drift-check test compares the two byte-for-byte and confirms parity.
- **OpenClaw coupling preserved:** pipeline write paths
  (`~/.satiety-pipeline/outbox/tool-requests/pending/` and `resolved/`),
  catalog lookup (`~/satiety-docs/TOOL-CATALOG.md`), WhatsApp
  notification step, worked examples naming Alfred and MailerLite by
  name, file-naming convention `YYYY-MM-DD-HHMM-<short-slug>.md`.
  Consumer (N6 `POST /recommend` compose step) handles any
  adapter-specific substitution.
- **Header style:** pointer-style per SESSION-2026-04-21-02 pattern-
  checkpoint decision. Per-fragment facts only; refers to
  `core/prompts/tool_awareness.py` for the full shared conventions.
  Pattern for X6/X7/X8 follows suit.
- **Session:** `SESSION-2026-04-21-02`.
- **Extractor:** Claude Code Opus 4.7 (`claude-opus-4-7[1m]`).
- **Verify with:** `pytest tests/test_prompts.py::TestToolRecommendationFragment`
