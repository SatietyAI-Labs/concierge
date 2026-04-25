# Repository structure audit (Day 8 Task 2 — surface findings only)

*Day 8 (2026-04-29) Pre-public-push prep block, Task 2 — read the
repo top-level as if landing on the GitHub page for the first time;
flag what reads weird to a stranger. **No remediation taken.** End-
of-day batches Task 0 sanitization + this audit's structural
recommendations together. Day 9 README work consumes this doc as
input.*

## Executive summary

The repo's **internal organization is competent** — directory
naming is mostly self-documenting; the `core/` / `adapters/` /
`tests/` / `alembic/` / `ui/` Python project shape is conventional;
git hygiene is clean (audit confirmed in Task 0). What reads weird
to a stranger is **public-presentation surface**, not internal
shape:

1. **`README.md` is a 3-line stub** while `CLAUDE.md` carries 180
   lines of substantive build-narrative — the public face is far
   thinner than the internal documentation. (Day 9 fixes.)
2. **`_legacy/` ships 8 dangling symlinks** pointing at external
   `/home/satiety/...` paths that do not exist on a stranger's
   clone. Per Task 0's lean: gitignore + `git rm --cached`. Confirmed.
3. **`docs/` and `planning/` boundary is unclear** — `docs/`
   currently contains build-strategy specs (blueprint, plan,
   operations protocol), not user-facing docs; `planning/` contains
   build-narrative (sessions, decisions, audits, summary docs). The
   two folders carry overlapping shapes, which a reviewer would
   flag. Two reasonable resolutions; recommendation surfaced below.
4. **`ui/` is empty** (only `__init__.py`) despite Vision section
   naming "Operator UI" as one of three v1 deliverables. UI work
   was Day 4 territory per the operations protocol but didn't land
   in the build that closed Bucket A on Day 7. A stranger sees an
   unfulfilled promise.
5. **No `LICENSE`** — public repos generally need one or default to
   "all rights reserved" (most-restrictive). Day 9 README +
   licensing decision.
6. **Hackathon framing tension** — `README.md` says "Hackathon
   entry"; `CLAUDE.md` says "Targeting: Built with Opus 4.7
   hackathon, April 21-26, 2026"; planning docs say "hackathon
   week." But Vision section frames the project as a "harness-
   agnostic, model-agnostic substrate" — much broader scope. The
   hackathon framing undersells, and the dates are now stale (Day 8
   logical-day = 2026-04-29).
7. **Several CLAUDE.md ground rules are operator-specific** (e.g.
   "Honor the filesystem split. Code on Windows, runtime on native
   WSL.") — applicable to one operator, confusing for a stranger.

**Nothing structurally blocks public push.** All findings have
clean dispositions; many are Day 9 README/LICENSE work, several
batch with Task 0 end-of-day remediation, and a couple are
genuinely structural (planning/docs boundary, `_legacy/` removal).
None are scrub-history operations.

---

## Surface 1 — `_legacy/` disposition

**Confirmed pre-flight finding from Task 0:** `_legacy/` is 8
symlinks; targets are external paths that don't exist on stranger
clones; the symlink target *strings* are committed as git symlink
metadata but the targeted *content* is not.

```
_legacy/agent-skills        → /home/satiety/.agent-skills
_legacy/moltbot-memory-mcp  → /home/satiety/moltbot-memory-mcp
_legacy/openclaw-root       → /home/satiety/.openclaw
_legacy/openclaw-workspace  → /home/satiety/.openclaw/workspace
_legacy/satiety-docs        → /home/satiety/satiety-docs
_legacy/satiety-pipeline    → /home/satiety/.satiety-pipeline
_legacy/tool-requests       → /home/satiety/.satiety-pipeline/outbox/tool-requests
_legacy/toolconcierge       → /mnt/c/Users/satie/Projects/ClaudeCodeCLI/ToolConcierge
```

**To a stranger:** an awkward 8-entry dir of broken symlinks. Some
strangers would interpret as broken; others as private-archive-not-
intended-for-them.

**To Lewie:** local-only navigation aid that maps Concierge's
historical lineage to the source workspaces still on his machine.
Useful in operator workflow; useless publicly.

**Recommended disposition (confirming Task 0 lean):** **gitignore +
`git rm --cached _legacy/<each>`**. Specifics:
- Add `_legacy/` to `.gitignore`
- `git rm --cached _legacy/<each>` to remove the 8 symlink metadata
  entries from the index without touching Lewie's working tree (he
  keeps his navigation aids; public repo doesn't see them)
- Single commit; commit body documents the structural rationale and
  cites this audit
- The symlinks' content was never in git (only metadata), so no
  history-rewrite is needed; old commits' symlink metadata stays in
  the audit trail per the decision-edit pattern's "prior-day entries
  stay intact" rule

**Alternative considered:** keep `_legacy/` symlinks as-is in the
public repo with a README explaining the historical-context aid.
Rejected: dangling symlinks are an active smell (linters, IDE
indexers, GitHub's own file viewer will flag them as broken). The
historical narrative belongs in CLAUDE.md / planning/ docs, not in
broken filesystem references.

**Coordinates with Task 0:** Task 0 Finding 3.2 surfaced the same
disposition. Both audit findings converge on this remediation; the
end-of-day commit can land both in one structural-cleanup pass.

---

## Surface 2 — `planning/` vs `docs/` boundary

**Current state inventory:**

`planning/` (30 tracked files):
- 7 root summary docs: `architecture-map.md`, `build-plan.md`,
  `classification.md`, `dependency-graph.md`, `executive-summary.md`,
  `gap-analysis.md`, `inventory.md`
- `today.md` (current-day plan)
- `sessions/` — 14 SESSION-YYYY-MM-DD-NN.md handoff snapshots
- `decisions/` — `DECISIONS.md` (1 file, 2906 lines, central
  architectural decision log)
- `audits/` — 1 file (`AUDIT-2026-04-23-blueprint-coverage.md`)
- `test-fixtures/` — 6 files (canonical soak-baseline corpus per
  ops-protocol §Test-fixture management)

`docs/` (9 tracked files):
- 5 current root docs: `concierge-blueprint-v2.md`,
  `concierge-claude-code-plan-v3.md`,
  `concierge-operations-protocol.md`,
  `close-the-gap-plan-2026-04-23.md`,
  `handoff-2026-04-23-scope-pivot.md`
- `archive/` — 4 historical files (3 superseded planning docs + 1
  `ARCHIVED.md` index)

**The boundary is unclear.** `docs/` contains build-strategy specs
(blueprint, plan, operations protocol) — these read like they
belong with the rest of the build-narrative in `planning/`.
`planning/` contains spec-shaped material too (architecture-map,
classification) — these read like they belong with the v2/v3 specs
in `docs/`. There is no pattern that separates which "build doc"
ends up where.

**Where a stranger lands:** Both folders ship publicly. Both are
build-narrative. Neither contains user-facing documentation (no
install guide, no API reference, no usage examples). A reviewer
inspecting both would notice the duplication of shape and ask "why
two folders?"

**Three resolutions, with my lean:**

**Option A (lean) — Move build-strategy docs from `docs/` to
`planning/`; leave `docs/` empty (or a stub) until v1 user-facing
docs are written.**
- Move: `concierge-blueprint-v2.md`, `concierge-claude-code-plan-v3.md`,
  `concierge-operations-protocol.md`, `close-the-gap-plan-2026-04-23.md`,
  `handoff-2026-04-23-scope-pivot.md` → `planning/`
- Move: `planning/archive/` → `planning/archive/`
- `docs/` becomes empty. Day 9 README work populates it with
  user-facing content (install guide, API docs, usage examples).
- Single rule: `planning/` is build-narrative; `docs/` is user-
  facing.
- **Why I lean this way:** the v1 release needs user-facing docs in
  `docs/`; the build-narrative is specifically not for end users.
  This is the tightest split that scales as the project matures.

**Option B — Move build-narrative from `planning/` to `docs/`,
consolidate.**
- All build-narrative under `docs/`. `planning/` becomes empty (or
  hosts only the current-day `today.md` if Lewie wants to keep
  per-day planning separate).
- Inverts the convention: `docs/` becomes both build-strategy AND
  user-facing.
- **Why I don't lean here:** loses the separation between "for the
  build" and "for end users." User-facing docs at v1 time would
  share a folder with 14 SESSION-*.md handoff snapshots, which is
  noisy.

**Option C — Document the current split explicitly; don't move
files.**
- Add a `planning/README.md` and `docs/README.md` that explain
  what's where and why.
- **Why I don't lean here:** the split itself is arbitrary; a
  README for it adds documentation overhead to an arrangement that
  doesn't serve a purpose. Documenting an arbitrary split entrenches
  it; better to fix the underlying shape.

**Specific items worth surfacing:**

- `planning/today.md` — daily plan. After Day 9, this file becomes
  stale unless it's continuously updated. Either move out of `git`-
  tracked planning (gitignore as ephemeral state) OR archive at end
  of build week. Per the operations protocol §Daily rhythm, this
  is the morning artifact — it has narrative value while the build
  is active, but post-build it's a pointer to a process that's
  ended.

- `planning/test-fixtures/` — these are NOT planning artifacts;
  they're load-bearing test corpus per `ops-protocol §Test-fixture
  management`. Used by `tests/test_smoke_live_anthropic.py` and the
  48h soak baseline. **Recommended:** move to `tests/fixtures/` or
  top-level `fixtures/`. Currently only `tests/fixtures/
  mock_mcp_backing_server.py` lives in `tests/fixtures/`, so
  consolidation is clean. The test-fixtures README's framing
  ("known-good corpus for soak observability") makes more sense
  alongside `tests/`, not under `planning/`.

- `planning/audits/` (1 file) and `planning/scratch/` (gitignored)
  — both are build-process artifacts. Keep under `planning/` per
  Option A.

**Coordinates with Day 9:** Whichever option Lewie chooses, the
README that Day 9 writes needs to reflect the chosen layout. A
`docs/README.md` index of "what's in this folder" is a natural
artifact for Day 9 if Option A lands.

---

## Surface 3 — Top-level files

**Currently tracked at repo root (alphabetized):**

| File | Lines | Stranger's read |
|---|---|---|
| `.gitignore` | 62 | Expected; well-shaped (covers caches, venvs, IDE files, env files, secrets-defense-in-depth, logs, scratch). Clean. |
| `CLAUDE.md` | 180 | Substantive — build-narrative, ground rules, vision. **But operator-specific** in places (filesystem split, daily drivers, brand context). A stranger's first read assumes this is the project README; expectation mismatch. |
| `README.md` | 3 (77 bytes) | **STUB.** "Hackathon entry — platform-agnostic AI tool concierge system." That's the entire content. Day 9 fixes. |
| `alembic.ini` | 150 | Standard Alembic generated config. Clean. No credentials per Task 0 audit. |
| `pyproject.toml` | 46 | Clean. Description: "Platform-agnostic tool awareness layer for AI agents" — accurate and public-safe. (Notably more descriptive than the current README.) |
| `uv.lock` | 3058 | Standard for uv projects; large because of torch/sentence-transformers/chromadb dep tree. Clean. |

**Missing public-repo expectations:**
- **`LICENSE`** — required for public release (legal default
  without one is "all rights reserved," restrictive). Day 9
  decision: which license? (Common choices: MIT, Apache 2.0, BSD-3.)
- **`CHANGELOG.md`** — optional. Pre-1.0 projects often skip until
  first release.
- **`CONTRIBUTING.md`** — optional. Useful if the project intends
  to accept contributions; can be deferred until contribution
  workflow is defined.
- **`CODE_OF_CONDUCT.md`** — optional.
- **`.github/`** — optional. Issue templates, PR templates, CI
  workflows. Day 9-10 territory.

**Notable presence (not strictly an issue, worth surfacing):**
- `CLAUDE.md` is at top-level. This is a Claude-Code convention
  (the file gets auto-loaded by Claude Code sessions). Other AI-
  tool-aware repos sometimes have `.cursor/rules`, `.aider`, etc.
  CLAUDE.md being top-level is fine; the question is what's IN it
  (see Surface 5 — operator-specific content).

**Recommended disposition:**
- README.md — Day 9 (rewrite from stub to substantive)
- LICENSE — Day 9 (add)
- CLAUDE.md — keep at top-level; **prune operator-specific content**
  (see Surface 5 below); consider moving most build-narrative into
  `planning/CLAUDE.md` or similar with the top-level CLAUDE.md
  becoming a thin pointer
- CONTRIBUTING.md / CHANGELOG.md / CODE_OF_CONDUCT.md — defer to
  post-v1 or per Lewie's preference

---

## Surface 4 — Directory naming clarity

**Self-documenting (clear to a stranger without context):**

| Directory | File count | Stranger's read |
|---|---|---|
| `core/` | 56 | Generic "main package." Standard. |
| `core/api/` | 9 | REST API. Clear. |
| `core/recommend/` | 8 | Recommendation engine. Clear. |
| `core/prompts/` | 7 | Prompt fragments. Clear. |
| `core/install/` | 7 | Install dispatcher. Clear. |
| `core/ingest/` | 4 | Ingestion logic. Clear. |
| `core/db/` | 4 | Database layer. Clear. |
| `tests/` | 59 | Standard. |
| `adapters/` | 19 (all under `claude_code/`) | Adapter pattern. Clear (and the empty space implies future adapters per blueprint v2 — OpenClaw + Claude Desktop). |
| `alembic/` | 9 | DB migration tool. Clear (anyone who's used Alembic recognizes it). |
| `scripts/` | 2 | After Task 1 deleted `concierge-shim`, only `recommend_live_smoke.py` + `verify_denial_recall.py`. Clear (verification scripts). |

**Slightly clunky but acceptable:**

- `core/lifecycle_store/` (6 files) — the `_store` suffix is an
  implementation detail leaking into the package name. Could just
  be `core/lifecycle/`. Minor; renaming would touch many imports;
  not worth the churn unless other refactors are happening anyway.

**Reads weird to a stranger:**

- `_legacy/` — the underscore prefix signals "historical / not
  authoritative current vision," which is the right semantic.
  But for stranger consumption, the symlinks themselves are the
  weird part (Surface 1).
- `ui/` — directory exists, contains only `__init__.py`. Empty
  package. Reads as "promised but not delivered" — see Surface 5.

**Recommended disposition:**
- Keep current naming for `core/*` and other dirs.
- Defer `core/lifecycle_store/` → `core/lifecycle/` rename to a
  future clean-up commit (low priority; not Day 8 scope).
- `_legacy/` and `ui/` covered by Surface 1 and Surface 5.

---

## Surface 5 — Inconsistencies a reviewer would flag

### 5a. `README.md` vs `CLAUDE.md` asymmetry

`README.md`: 3 lines, 77 bytes. Just a tagline.
`CLAUDE.md`: 180 lines, ~10.9KB, substantive.

A stranger landing on the GitHub page sees the README as the
authoritative project description; finding a richer, more detailed
CLAUDE.md inside the repo creates expectation mismatch. The
substantive content lives in the AI-tool-specific file, not the
human-readable file.

**Recommended disposition:** Day 9 README work resolves this. The
README needs to carry the project's public-facing narrative
(vision, what it does, install instructions, basic usage). CLAUDE.md
becomes a thinner doc focused on AI-session-specific instructions.

### 5b. "Hackathon" framing tension

- `README.md`: "Hackathon entry — platform-agnostic AI tool
  concierge system."
- `CLAUDE.md` line ~166: "Targeting: Built with Opus 4.7 hackathon,
  April 21-26, 2026"
- `CLAUDE.md` line ~167: "Plan: substantively done by Day 4 (Friday),
  Days 5-6 for stabilization and demo polish"
- Many planning docs reference "hackathon week"

But:
- `CLAUDE.md` Vision section frames the project as a "harness-
  agnostic, model-agnostic tool-awareness substrate" — much broader
  scope than a hackathon entry
- The build extended through Day 7 (logical-day 2026-04-28) and
  Day 8 today is `2026-04-29`. The "April 21-26" target is stale by
  3+ days and the "substantively done by Day 4 (Friday)" plan was
  superseded by the operational-first pivot per `DECISIONS [2026-04-21
  18:00]`
- Day 8 work is explicitly "Pre-public-push prep" — the hackathon's
  over but the project continues

**Recommended disposition:** Day 9 README should drop "hackathon
entry" framing and lead with the harness-agnostic-substrate vision.
CLAUDE.md should update the dates section to reflect the actual
extended timeline OR drop specific dates entirely (the build-week
context is captured in `planning/today.md` + SESSION snapshots; the
ground-rules don't need a date). The hackathon framing remains
accurate as historical-origin context (worth keeping in the README's
"about" section as origin-story), but it's no longer the project's
current frame.

### 5c. `ui/` directory unbuilt

Vision section names "Operator UI" as one of three v1 deliverables:
"a real, browser-accessible interface with three sections for v1:
Tool Registry, Pending Requests Inbox, Health/Stats bar. Built with
FastAPI + HTMX + Pico.css."

Operations protocol §Phase checkpoint criteria, "Build Day 4
(Friday) — Substantive completion target," lists:
- UI loads in browser at localhost
- Tool Registry section shows packs and sub-tools, expandable
- Pending Requests Inbox renders requests, approve/deny/defer
  buttons work via HTMX
- Health/Stats bar at top displays live data

But `ui/` contains only `__init__.py` (1 file). UI work didn't land
in the build that closed Bucket A on Day 7. A stranger sees an
unfulfilled promise.

**Recommended disposition options:**

(i) **Acknowledge** — README + CLAUDE.md note that UI is deferred
to a future phase; current v1 surface is the MCP shim + HTTP API.
Cheapest fix; honest about scope.

(ii) **Build the UI** — Day 9 or Day 10+ work. Fulfills the
original v1 promise. Most expensive but matches stated scope.

(iii) **Drop UI from scope** — Update Vision section to remove
"Operator UI" as a v1 deliverable. Reframe to "MCP-first; UI
deferred to v1.1 or later." Requires a DECISIONS entry to close
the scope-change loop.

(i) is the least-effort path that keeps the public framing honest;
(ii) is best if Lewie wants UI to actually exist before public
push; (iii) is the cleanest if UI is genuinely out of scope.
**Surface this for case-by-case decision** — I don't have visibility
into Lewie's UI-scope intent post-build-week.

### 5d. CLAUDE.md operator-specific ground rules

CLAUDE.md ground rule 7: "Honor the filesystem split. Code on
Windows, runtime on native WSL."

This is operator-environment-specific (Lewie's WSL2-on-Windows
setup). On a fresh-clone on macOS/Linux/Windows-native, this rule
is meaningless or actively misleading.

CLAUDE.md "Personal context" section names:
- Lewie's brands (SatietyAI, Sonoran Caramel Co, Bartruff)
- Daily drivers (Claude Code CLI, Claude Desktop, Cowork tab)
- "13 months into AI"
- "Has never built a UI before"
- WSL2 multi-machine setup

This is operator-context that doesn't translate to a public reader.
It helped past-Claude-Code-sessions calibrate to Lewie's expertise
and constraints; it doesn't help anyone else.

**Recommended disposition:** prune operator-specific content from
CLAUDE.md as part of Day 9 work. Either:
- Move the operator-specific section to a separate
  `planning/operator-context.md` (Lewie-personal; possibly
  gitignored)
- OR keep CLAUDE.md but rewrite it as "AI-session ground rules for
  Concierge contributors" — generic enough to apply to any future
  contributor, not just Lewie

### 5e. Stale planning/today.md after Task 1 close

`planning/today.md` line 41 references `scripts/concierge-shim` in
the Task 1 description (now-historical state of a completed task).
Per the ops-protocol decision-edit pattern, the *historical-record*
in SESSION snapshots and DECISIONS entries stays intact. But
`today.md` is the current day's planning artifact — it gets rewritten
each day. Updating it to reflect Task 1's completion is consistent
with the daily-rhythm model.

**Recommended disposition:** when the Day 8 SESSION snapshot is
written end-of-day, `today.md` rolls forward to Day 9's plan. The
Task 1 description's stale reference becomes a non-issue. (This is
already handled by the standard process; flagging here for
completeness.)

### 5f. "Lewie" / "satiety" / "satietyllc" usage

Per Lewie's Class-2 calibration in Task 0, operator-identifying
strings (`satiety` username, `Lewie` operator name) are explicitly
**not scrub targets**. The repo name will publicly associate with
him on push regardless.

**Surfaced for completeness, no remediation:** the build-narrative
naturally names "Lewie" as the operator (commit messages, planning
docs, decision log narration). This is consistent with the brand-
publicity goal and stays as-is.

### 5g. CLAUDE.md says core/ is "empty during planning"

CLAUDE.md "Output locations" section:
- "core/ — empty during planning. Platform-agnostic Concierge service."
- "adapters/claude-code/ — empty during planning. Claude Code adapter."
- "ui/ — empty during planning. FastAPI + HTMX UI."

These statements were true Day 0 but are now stale: `core/` has 56
files, `adapters/claude_code/` has 19. Only `ui/` actually remains
empty.

**Recommended disposition:** prune these stale "empty during
planning" statements from CLAUDE.md as part of Day 9 cleanup. Keep
the directory-purpose annotations; drop the build-week-only state
descriptors.

### 5h. `planning/inventory.md`, `architecture-map.md`,
`classification.md` etc. are Phase A-F deliverables

These exist because the build week followed a phased approach
(Phase A inventory → Phase B architecture map → Phase C classify →
Phase D dependency graph → Phase E gap analysis → Phase F build
plan). They're milestone artifacts of a process that's now over.

**Surface only — no recommendation:** they're build-narrative;
they ship publicly; they convey the project's deliberate-design
character. Keep them. (This is informational, not actionable.)

### 5i. `pyproject.toml` description vs README description

`pyproject.toml`: "Platform-agnostic tool awareness layer for AI
agents."

`README.md`: "Hackathon entry — platform-agnostic AI tool concierge
system."

Two slightly different framings of the same project. Day 9 README
work should harmonize.

---

## Recommendations table

| # | Finding | Disposition | Coordinates with | Day owner |
|---|---|---|---|---|
| 1 | `_legacy/` 8 dangling symlinks | gitignore + `git rm --cached` | Task 0 Finding 3.2 | Day 8 end-of-day batch |
| 2 | `docs/` vs `planning/` boundary unclear | Option A: move build-strategy docs from `docs/` to `planning/`; reserve `docs/` for v1 user-facing | — | Day 9 (if Option A); decide before README work |
| 3 | `planning/test-fixtures/` shouldn't live in `planning/` | Move to `tests/fixtures/` (consolidation with existing `tests/fixtures/mock_mcp_backing_server.py`) | — | Day 9 or end-of-day batch |
| 4 | README.md is a 3-line stub | Rewrite per Vision section + install/usage docs | Surface 5a, 5b | Day 9 |
| 5 | LICENSE missing | Add (license choice TBD) | — | Day 9 |
| 6 | CLAUDE.md operator-specific ground rules and personal-context | Prune operator-specific content; either move to `planning/operator-context.md` or rewrite CLAUDE.md generically | Surface 5d | Day 9 |
| 7 | "Hackathon entry" framing in README + CLAUDE.md | Drop in favor of harness-agnostic-substrate framing; keep hackathon-origin as historical context | Surface 5b | Day 9 |
| 8 | CLAUDE.md "April 21-26, 2026" target date stale | Drop specific dates OR update to reflect extended timeline | Surface 5b | Day 9 |
| 9 | CLAUDE.md "empty during planning" stale statements | Prune for `core/` and `adapters/claude_code/`; either drop or reframe for `ui/` | Surface 5g | Day 9 |
| 10 | `ui/` directory empty despite Vision-named v1 deliverable | Decision: acknowledge-as-deferred / build / drop-from-scope | Surface 5c | Lewie decision; Day 9 README reflects |
| 11 | `pyproject.toml` description vs README description framing mismatch | Harmonize during README rewrite | Surface 5i | Day 9 |
| 12 | `core/lifecycle_store/` clunky `_store` suffix | Defer to future cleanup commit | — | Not Day 8/9; future |
| 13 | `today.md` references deleted `scripts/concierge-shim` | Resolves naturally when Day 9 today.md replaces Day 8 today.md | Surface 5e | Day 9 (auto) |

---

## Coordination notes (Task 0 + Task 2 batching)

**End-of-day remediation phase** batches the following from Task 0:

- Worked-example sanitization across `core/prompts/*.py` files
  (generic scenarios; not GHL-substituted; per Lewie's Option B
  reframe in Task 0 close-out)
- ElevenLabs anti-bot paragraph (`soul_delta.py:127-128`) wholesale
  replacement
- MailerLite-specific tool-IDs / `Alfred (port 18789)` /
  fleet-topology generic-ization
- New DECISIONS entry: "EXTRACT invariant retired pre-public-push"
- `tests/test_prompts.py` byte-identity test retirement (lean α
  delete)
- `core/prompts/SKILL_FRAGMENT_SYNC_LOG.md` historical-note
  conversion (lean β preserve)
- Full suite re-run post-sanitization

**Plus from Task 2:**

- `_legacy/` gitignore + `git rm --cached` (Surface 1, item 1)
- Optional: `planning/test-fixtures/` → `tests/fixtures/` move
  (Surface 2, item 3) — small, mechanical, can ride along
- Optional: build-strategy docs `docs/` → `planning/` move
  (Surface 2, item 2 / Option A) — bigger; might warrant its own
  commit for diff readability

**Commit-shape recommendation for end-of-day:** at minimum two
commits:
1. **`refactor(prompts): retire EXTRACT invariant + sanitize worked examples`** —
   the load-bearing public-readiness commit. Includes the prompt
   fragment rewrites + DECISIONS entry + test retirement +
   SKILL_FRAGMENT_SYNC_LOG conversion. Single coherent payload.
2. **`chore(repo): gitignore _legacy/ + relocate test-fixtures`** —
   structural cleanup. Smaller, mechanical.

If Option A from Surface 2 lands today (`docs/` vs `planning/`
reorganization), recommend a third commit:
3. **`chore(docs): move build-strategy docs from docs/ to planning/`** —
   pure relocation; large diff but mechanical (`git mv` operations).

Lewie's call on whether commit 3 is in-scope today or Day 9.

---

## Day 9 forward-pointers

Items where this audit surfaces a documentation/decision requirement
that Day 9 README work needs to address explicitly:

1. **README rewrite** — substantive replacement of the 3-line stub.
   Source material: Vision section of CLAUDE.md, blueprint-v2,
   and pyproject.toml description. Drop hackathon-entry framing;
   lead with harness-agnostic-substrate. Include install + usage.
   Reference the operator action from Task 1's commit (`uv sync
   --extra dev` + Claude Code MCP config registration via the
   `concierge-shim` console-script entry-point) — Task 1's commit
   body already flagged this as a forward-pointer.

2. **LICENSE choice** — pre-Day-9 decision. Common candidates: MIT
   (most permissive), Apache 2.0 (patent grant + permissive),
   BSD-3-Clause (permissive without patent grant), AGPL (copyleft
   for network-served software). Decision warrants a DECISIONS
   entry.

3. **`docs/` vs `planning/` boundary decision** (Surface 2 Option
   A/B/C) — should land BEFORE Day 9 README work, since Day 9
   README references the layout chosen.

4. **UI scope decision** (Surface 5c, item 10) — three options
   (acknowledge-deferred / build / drop). Decision shapes Day 9
   README's "what's in v1" framing.

5. **CLAUDE.md prune scope** — Day 9 CLAUDE.md cleanup pairs with
   the README rewrite. Items: operator-specific ground rules,
   personal context, stale "empty during planning" statements,
   stale dates, hackathon framing.

6. **`pyproject.toml` description vs README harmonization** — minor
   but worth addressing during Day 9.

7. **CONTRIBUTING.md / CHANGELOG.md / `.github/` decisions** —
   Day 9 or Day 10. Lewie's preference on contribution surface.

---

## Negative findings (audit coverage record)

Explicit "checked X, found nothing structurally wrong" entries so
audit coverage is auditable:

- **No tracked binary files that shouldn't ship.** `concierge.db`,
  `.venv/`, `concierge.egg-info/`, `__pycache__/` all gitignored
  and not in `git ls-tree`.
- **No tracked credential-shape files** (per Task 0 audit): no
  `.pem`, `.key`, `.crt`, `.env`-style files in tree or history.
- **No dangling references to the deleted `scripts/concierge-shim`
  outside of historical record** — references survive only in
  prior-day SESSION snapshots, prior-day DECISIONS entries,
  `planning/handoff-2026-04-23-scope-pivot.md`, and the current-day
  `today.md`'s task description (which rolls forward at Day 9).
  These are decision-edit-pattern-compliant historical record.
- **No `.github/` or CI workflow files committed.** No CI is
  configured. (Decision: Day 9-10 territory.)
- **`alembic/` structure clean** — generic Alembic init layout +
  6 versioned migration files. No issues.
- **`tests/conftest.py` + 59 test files** — standard pytest layout.
  No structural issues.
- **`pyproject.toml` is well-shaped** — `[project]` metadata
  complete, `[project.scripts]` entry added in Task 1, deps and
  dev-extras pinned via `uv.lock`.
- **`scripts/` post-Task-1** — only the two live-smoke verification
  scripts remain. Both have docstrings explaining purpose. Acceptable.

The repo's **structural integrity is sound.** The findings are
public-presentation surface, not structural defects. End-of-day
remediation closes the public-presentation gap; Day 9 fixes the
documentation gap.
