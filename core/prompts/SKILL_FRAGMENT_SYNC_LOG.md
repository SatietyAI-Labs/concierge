# Skill-Extract Sync Log

*Filename retained as `SKILL_FRAGMENT_SYNC_LOG.md` for git-history
continuity; scope now covers both extract classes — see below.*

Governing decision: **DECISIONS `[2026-04-21 05:50]`** — *Skill-extraction
pattern: EXTRACT as prompt fragments (not pure Python, not ADAPT).*
This file implements structural mitigation #2 from that entry.

## Two extract classes

The sync log tracks two kinds of extract:

### Class 1 — `prompt-fragment`

A Python string constant in `core/prompts/*.py` that holds verbatim
markdown body (or a verbatim section of it) from a skill file. The
constant is composed into `POST /recommend`'s Opus 4.7 system
prompt. Established by X3/X4/X6 as whole-body extracts; X7-A
introduces the selective-section variant.

### Class 2 — `python-constants`

A Python module with semantically-named values (ints, frozensets,
tuples, dicts) re-authored from structured data that the skill
file's prose describes. The constants are consumed by Python code
(lifecycle scanners, endpoints, cron) — not by Opus. First extract
in this class: X7-B (`core/lifecycle_policy.py`).

### How the classes differ

| Dimension | `prompt-fragment` | `python-constants` |
|---|---|---|
| Scope | whole-body or selective-by-H2 | selective by definition |
| Naming | verbose `_PROTOCOL__FROM_*` for grep-drift | plain semantic names |
| Fidelity | verbatim markdown | values re-authored from prose |
| Drift check | byte-for-byte vs source (or sliced section) | source-cross-check asserts the prose that anchors each value still appears in source |
| Consumer | Opus 4.7 system prompt | Python code |
| Module home | `core/prompts/<name>.py` | application module (e.g. `core/lifecycle_policy.py`) |
| Test home | `tests/test_prompts.py::Test<…>Fragment` | `tests/test_<area>.py` |

## Purpose

Make source-of-truth drift between OpenClaw-side skill files (under
`_legacy/`) and Concierge-side extracts visible to a reader of this
log alone, without requiring them to diff file contents.

## Drift models (hackathon week)

Both classes use manual re-sync per DECISIONS `[2026-04-21 05:50]`
mitigation #4.

### `prompt-fragment` re-sync

When a source skill file changes:
1. Re-read the source body (or selected section for a selective extract).
2. Re-paste verbatim into the corresponding constant in
   `core/prompts/<fragment>.py`.
3. Update the Source SHA-256 / mtime / bytes lines in that module's
   header comment block.
4. Update the fragment's row under §Current prompt fragments.
5. Append a new entry under §Sync history describing the change.
6. Re-run the test suite named in that entry's `Verify with:` line.

### `python-constants` re-sync

When a source skill file changes:
1. Re-read the source prose that anchors each constant.
2. Re-author the values in `core/<module>.py` if the source's stated
   values have changed (e.g. threshold `5` → `6`).
3. If any source-anchor phrase has been reworded, update the
   corresponding assertion in the source-cross-check tests.
4. Update the Source SHA-256 / mtime / bytes lines in the module
   header.
5. Update the constants' row under §Current python constants.
6. Append a §Sync history entry.
7. Re-run the test suite named in that entry's `Verify with:` line.

**Cross-class coupling:** when a source file has both a prompt-fragment
and python-constants extract (as tool-lifecycle does with X7-A and
X7-B), a source change may require **joint re-sync** of both extracts.
The source-cross-check tests are the primary signal that this has
happened — their failure indicates the prose has changed, which in
turn means the prompt fragment probably has too.

## Phase 2 deferred target

Build-time regeneration via `make sync-prompts`. The generator would
read YAML front-matter or HTML-comment markers in the source skill
file to determine extraction boundaries, then regenerate each
`core/prompts/<fragment>.py` module (for fragments) or surface
anchor-phrase changes that warrant constants re-authoring (for
python-constants). This eliminates the manual re-sync step and
most of the drift risk. Named and deferred per DECISIONS
`[2026-04-21 05:50]` §"Phase 2 structural improvement path."

---

## Current prompt fragments

| # | Constant | Module | Source (repo-relative) | Source SHA-256 (first 8) | Source mtime | Source bytes | Scope | Extracted |
|---|---|---|---|---|---|---|---|---|
| X3 | `TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD` | `core/prompts/tool_awareness.py` | `_legacy/agent-skills/shared/tool-awareness.md` | `7d1d2f04` | 2026-03-24 11:21 PDT | 9619 | whole body | 2026-04-21 15:43 PDT (SESSION-2026-04-21-02) |
| X4 | `TOOL_RECOMMENDATION_PROTOCOL__FROM_TOOL_RECOMMENDATION_MD` | `core/prompts/tool_recommendation.py` | `_legacy/agent-skills/shared/tool-recommendation.md` | `a014fe22` | 2026-04-13 18:03 PDT | 9571 | whole body | 2026-04-21 16:14 PDT (SESSION-2026-04-21-02) |
| X6 | `TOOL_DISCOVERY_PROTOCOL__FROM_TOOL_DISCOVERY_SKILL` | `core/prompts/tool_discovery.py` | `_legacy/openclaw-workspace/skills/tool-discovery/SKILL.md` | `64b9b365` | 2026-04-13 20:46 PDT | 5223 | whole body | 2026-04-21 16:25 PDT (SESSION-2026-04-21-02) |
| X7-A | `TOOL_LIFECYCLE_WEEKLY_REVIEW_PROTOCOL__FROM_TOOL_LIFECYCLE_SKILL` | `core/prompts/tool_lifecycle.py` | `_legacy/openclaw-workspace/skills/tool-lifecycle/SKILL.md` | `79128223` | 2026-04-13 21:09 PDT | 7158 | selective (`## Weekly review`, 862 bytes) | 2026-04-21 16:50 PDT (SESSION-2026-04-21-02) |

---

## Current python constants

| # | Module | Source (repo-relative) | Source SHA-256 (first 8) | Source mtime | Source bytes | Extracts (named constants) | Extracted |
|---|---|---|---|---|---|---|---|
| X7-B | `core/lifecycle_policy.py` | `_legacy/openclaw-workspace/skills/tool-lifecycle/SKILL.md` | `79128223` | 2026-04-13 21:09 PDT | 7158 | `TOOL_SELECTION_MEMORY_TAG`, `TOOL_SELECTION_STATUS_VALUES`, `TOOL_SELECTION_STATUS_TRANSITIONS`, `TOOL_SELECTION_CONTENT_FIELDS`, `PROMOTION_MIN_USES`, `PROMOTION_WINDOW_DAYS`, `DEMOTION_INACTIVITY_DAYS`, `STALE_PENDING_DAYS` | 2026-04-21 16:50 PDT (SESSION-2026-04-21-02) |

---

## Sync history

History is append-only and chronological across both classes. Each
entry names the class, the extract, the provenance, and the verify
command.

### `2026-04-21 15:43 PDT` — X3 initial extract *(class: prompt-fragment)*

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
  format) is the canonical reference for every subsequent
  prompt-fragment extract.
- **Verify with:** `pytest tests/test_prompts.py::TestToolAwarenessFragment`

### `2026-04-21 16:14 PDT` — X4 initial extract *(class: prompt-fragment)*

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
  Pattern for X6/X7-A/X8 follows suit.
- **Session:** `SESSION-2026-04-21-02`.
- **Extractor:** Claude Code Opus 4.7 (`claude-opus-4-7[1m]`).
- **Verify with:** `pytest tests/test_prompts.py::TestToolRecommendationFragment`

### `2026-04-21 16:25 PDT` — X6 initial extract *(class: prompt-fragment)*

- **Constant:** `TOOL_DISCOVERY_PROTOCOL__FROM_TOOL_DISCOVERY_SKILL`
- **Module:** `core/prompts/tool_discovery.py`
- **Source:** `_legacy/openclaw-workspace/skills/tool-discovery/SKILL.md`
- **Source SHA-256:**
  `64b9b365ba2f9b66eb1832e17214d4599af426a5ba92d6b8f49919fc25a628ca`
- **Source mtime:** `2026-04-13 20:46:25 -0700`
- **Source bytes:** `5223`
- **Section extracted:** full document body below the YAML frontmatter
  (source lines 6-111). YAML `name:` / `description:` fields excluded
  (skill-loader metadata, not prompt content).
- **Fidelity:** VERBATIM. No backslash or triple-quote hazards in
  source; no escaping applied. Drift-check confirms byte-for-byte
  parity.
- **Demo-critical:** classification §C.5.3 flags this as the headline
  example of the prompt-fragment pattern — the green/yellow/red
  signal-table content is prompt-fragment material, not a Python
  scoring function. N8 smoke assertion (`csvstat > pandas` for
  "analyze a CSV") validates this fragment's effectiveness inside
  Opus 4.7's system prompt.
- **OpenClaw coupling preserved:** pipeline README path
  (`~/.satiety-pipeline/outbox/tool-requests/README.md`), catalog path
  (`~/satiety-docs/TOOL-CATALOG.md`), and the catalog section names
  ("Installed" / "Not Installed"). Lightest coupling footprint of the
  prompt-fragment set — worked example uses generic pandoc, no fleet
  agent names, no MCP tool IDs.
- **Constant naming note:** DECISIONS `[2026-04-21 05:50]` mitigation
  #3 suggested `DISCOVERY_SIGNALS__FROM_TOOL_DISCOVERY_SKILL` as an
  illustrative example, but that name only describes the signal-table
  subsection. Chose `TOOL_DISCOVERY_PROTOCOL__FROM_TOOL_DISCOVERY_SKILL`
  for structural consistency with X3/X4's `{SOURCE}_PROTOCOL__FROM_{…}`
  pattern, since this file also covers a whole-document protocol
  (search → evaluate → file → follow-up). Drift visibility (the
  governing requirement) is preserved.
- **Header style:** pointer-style (per X4 precedent). Refers to
  `core/prompts/tool_awareness.py` for the shared conventions.
- **Session:** `SESSION-2026-04-21-02`.
- **Extractor:** Claude Code Opus 4.7 (`claude-opus-4-7[1m]`).
- **Verify with:** `pytest tests/test_prompts.py::TestToolDiscoveryFragment`

### `2026-04-21 16:50 PDT` — X7-A initial extract *(class: prompt-fragment, first selective extract)*

- **Constant:** `TOOL_LIFECYCLE_WEEKLY_REVIEW_PROTOCOL__FROM_TOOL_LIFECYCLE_SKILL`
- **Module:** `core/prompts/tool_lifecycle.py`
- **Source:** `_legacy/openclaw-workspace/skills/tool-lifecycle/SKILL.md`
- **Source SHA-256:**
  `79128223564dcb63bc4c50763eefc6545e6151c7ccfb56a34d6a5adf895299d4`
- **Source mtime:** `2026-04-13 21:09:25 -0700`
- **Source bytes (whole file):** `7158`
- **Fragment bytes (extracted section):** `862`
- **Section extracted:** `## Weekly review` (inclusive) through
  end-of-file. Located in source at byte offset 6296; runs 862 bytes.
  YAML frontmatter is not in scope for a selective H2-slice extract —
  the slicer locates `## Weekly review` directly.
- **Fidelity:** VERBATIM of the sliced section. No backslash or
  triple-quote hazards; no Python-layer escaping applied. Drift-check
  compares against `_slice_section_by_h2(source, "Weekly review")`
  via the extended helper in `tests/test_prompts.py`.
- **Precedent-setting note:** this is the **first selective extract**
  in the prompt-fragment class. Earlier fragments (X3/X4/X6) extracted
  whole-body. The selective mode exists because X7 is a partial hybrid
  (classification §C.5.3) — only the weekly-review section is
  prompt-fragment material; the rest of the skill file is either
  python-constants (X7-B) or OpenClaw-side agent prose not consumed
  by Concierge. Future selective extracts cite X7-A as precedent and
  reuse `_slice_section_by_h2` or a similar helper.
- **OpenClaw coupling preserved:** housekeeping log path
  (`~/.satiety-pipeline/outbox/housekeeping.log`), WhatsApp
  notification at tail, MCP tool name `memory__memory_search`, and
  the numeric thresholds in prose form ("5+ occurrences in 30 days",
  "in 90 days", "older than 7 days"). Numeric drift between the
  prose-form here and the python-constants form in `core/lifecycle_policy.py`
  is detected by the source-cross-check test in `test_lifecycle.py`.
- **Header style:** pointer-style (per X4 precedent). Refers to
  `core/prompts/tool_awareness.py` for the shared conventions, plus
  adds an in-module "What is NOT in this fragment" block listing the
  sections left in `_legacy/` only.
- **Session:** `SESSION-2026-04-21-02`.
- **Extractor:** Claude Code Opus 4.7 (`claude-opus-4-7[1m]`).
- **Verify with:** `pytest tests/test_prompts.py::TestToolLifecycleWeeklyReviewFragment`

### `2026-04-21 16:50 PDT` — X7-B initial extract *(class: python-constants, FIRST OF CLASS)*

- **Module:** `core/lifecycle_policy.py`
- **Source:** `_legacy/openclaw-workspace/skills/tool-lifecycle/SKILL.md`
- **Source SHA-256:**
  `79128223564dcb63bc4c50763eefc6545e6151c7ccfb56a34d6a5adf895299d4`
- **Source mtime:** `2026-04-13 21:09:25 -0700`
- **Source bytes:** `7158`
- **Constants extracted:**
  - `TOOL_SELECTION_MEMORY_TAG = "tool-selection"`
  - `TOOL_SELECTION_STATUS_VALUES: frozenset[str]` (6 values)
  - `TOOL_SELECTION_STATUS_TRANSITIONS: dict[str, frozenset[str]]`
    (3 from-keys, 4 explicit transitions)
  - `TOOL_SELECTION_CONTENT_FIELDS: tuple[str, ...]`
    (6 fields, ordered per source template)
  - `PROMOTION_MIN_USES = 5`
  - `PROMOTION_WINDOW_DAYS = 30`
  - `DEMOTION_INACTIVITY_DAYS = 90`
  - `STALE_PENDING_DAYS = 7`
- **Sections drawn from:** "Storing a tool-selection memory", "Status
  values", "Updating memory entries", "Promotion criteria", "Demotion
  criteria", "What to check" (item 3).
- **Fidelity:** values re-authored from source prose. Not a verbatim
  markdown extract — this is the point of the class. The re-authored
  values are anchored to source via the source-cross-check tests.
- **Precedent-setting note:** **this is the first extract in the
  `python-constants` class.** Distinguishing it from the
  `prompt-fragment` class along five dimensions:
  1. *Scope* — selective by definition (no whole-body re-authoring
     exists); contrast with X3/X4/X6 which are whole-body verbatim.
  2. *Naming* — plain semantic names (`PROMOTION_MIN_USES`) vs the
     verbose `_PROTOCOL__FROM_*` drift-visibility suffix used for
     prompt fragments. Plain names are correct here because the
     provenance is in the module header; the drift surface is the
     source-cross-check test, not grep.
  3. *Fidelity* — values re-authored from prose. A prompt-fragment
     extract is byte-for-byte; a python-constants extract is
     semantic-for-semantic.
  4. *Drift check* — source-cross-check tests assert the anchor
     phrases (e.g. "Used 5+ times in the last 30 days") still appear
     in source. Prompt fragments use byte-for-byte verbatim matching
     against a sliced section.
  5. *Module home* — application module (`core/lifecycle_policy.py`), not
     `core/prompts/`. Prompt fragments belong in `core/prompts/`; a
     python-constants extract lives wherever its consuming code will
     live.

  Future selective or structured extracts cite X7-B as precedent
  for these distinctions.
- **Coupling footprint:** none in the constants themselves (they are
  structural data, not paths or names). Source prose that anchors
  the constants does contain OpenClaw-specific paths
  (`~/.satiety-pipeline/outbox/housekeeping.log`) but those live in
  the X7-A prompt fragment or remain in `_legacy/` only.
- **Cross-class coupling with X7-A:** both extracts derive from the
  same source file. A source edit that changes a threshold
  (e.g. "5+ times" → "6+ times") requires joint re-sync: X7-A's
  prompt fragment (the prose still mentions 5+) AND X7-B's Python
  constants (PROMOTION_MIN_USES). The source-cross-check test
  `test_promotion_criteria_phrase_in_source` fails in that scenario
  and is the primary signal that the joint re-sync is required.
- **Session:** `SESSION-2026-04-21-02`.
- **Extractor:** Claude Code Opus 4.7 (`claude-opus-4-7[1m]`).
- **Verify with:** `pytest tests/test_lifecycle.py`
