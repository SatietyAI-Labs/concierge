# Today — 2026-05-02 (Day 11 — Launch artifacts day)

*Opens on: `SESSION-2026-05-01-01.md` (Day 10 close-out — seven commits landing the operator dashboard: alignment `4c04797`, factory-only refactor `7ad9f7a`, Task 0 scaffolding `7686e6f`, Task 1 Health/Stats bar `e37a4e7`, Task 2 Tool Registry `aef135b`, Task 3 Pending Inbox + SSE `92336c2`, Task 4 index composition + CSS polish `f338cbb`. Suite at clean baseline 817/0/1/3. DECISIONS `[2026-05-01 Day 10]` covers UI architecture + v0.1 design-surface decisions. Live-verify completed by operator with four screenshots at `planning/scratch/day-10-screenshots/` for Day 11 demo recording inputs. Four forward-carries surfaced: uv run prefix, hx-indicator UX gap, approve-action 8s perf question, Health/Stats counter drift.)*

*Campaign-context reframing ratified at Day 11 alignment: Day 11 is a beat in an active multi-week SatietyAI brand-building campaign — not a one-shot launch. Concierge's launch is the kickoff beat for an agent-crew-managed distribution program across LinkedIn + YouTube with multiple funnels and lead magnets in active development, a pre-built audience trajectory, and SatietyAI mission framing (helping people build with AI for personal/professional development + small-business AI implementation). Day 11 produces a campaign content package — modular, remix-friendly, two-variant (LinkedIn + YouTube), with forward content seeds for subsequent campaign beats — alongside public-release housekeeping artifacts and Day-10 forward-carry polish.*

## Governing framing

Launch artifacts day. Three-task ladder: Task 1 = Day-10 forward-carry polish; Task 2 = public-release housekeeping artifacts; Task 3 = campaign content package (substantially expanded from "demo + blog draft" to fit the campaign-package target). Day 12 = final review + GitHub push.

**Runtime substrate is frozen for Day 11.** Public-release scaffolding (Day 9) and operator dashboard (Day 10) are both done. Day 11 changes touch one core API endpoint (Health/Stats counter SQL filter), one UI partial (action-button hx-indicator), README copy, CHANGELOG / CONTRIBUTING / issue templates (new files), and written content drafts at `planning/scratch/`. Recommend / SSE wire format / lifecycle store paths untouched.

**ABOUT.md mission framing is load-bearing across Task 3 content.** Concierge is infrastructure for the same mission as SatietyAI's teaching: making AI legible to people building with it. The lever / pulley / industrial-revolution rhetorical anchor connects Concierge to SatietyAI's mission directly.

## Day 11 — Launch artifacts day

**Primary goal:** Land three Day-10 forward-carry polish items (README uv run prefix, hx-indicator on action buttons, Health/Stats counter alignment to `Request.status == 'pending'`); land public-release housekeeping artifacts (CHANGELOG terse Keep-a-Changelog, CONTRIBUTING richer-with-pointers compressed, `.github/ISSUE_TEMPLATE/` Bug Report + Feature Request); produce campaign content package (demo recording two cuts on-camera, LinkedIn launch post, YouTube launch post, HackerNews submission draft, 3-5 content calendar seeds for the agent crew). DECISIONS bundled entry `[2026-05-02 Day 11]` written at close-out covering all day-11 design decisions per Day 7 ratified bundled-entry pattern. Day 11 SESSION close-out snapshot written; today.md updated to Day 12 placeholder.

## Tasks

### Task 1 — Day-10 forward-carry polish

Three sub-tasks, each landing as a clean single-purpose commit (bundled OK only if a sub-task naturally rides another's wiring tests):

**1.1 — README `uv run` prefix fix** (Fork B1)
- README install section currently assumes `uvicorn` resolves globally; false in WSL with uv-managed venv unless activated
- Update install + canonical-launch instructions to `uv run uvicorn ui.app:create_app --factory --reload --port 8000` (and the headless `core.app:create_app` form per Day 10 factory-only ratification)
- **Discipline:** read-after-edit on README.md to verify markdown structure preserved
- **Acceptance:** clone-into-fresh-WSL-shell + `uv sync` + canonical launch command boots cleanly to dashboard at `localhost:8000`

**1.2 — hx-indicator UX feedback on Approve/Deny/Defer action buttons** (Fork B2)
- Standard HTMX `hx-indicator` + button-disabled-during-request pattern on `ui/templates/partials/pending_inbox.html` action form
- Spinner element rendered in markup; visible during in-flight; CSS for spinner + button-disabled state transitions in `ui/static/css/concierge.css`
- **Wiring tests:** in-flight rendering wires `hx-indicator` attribute correctly; button-disabled state visible mid-request via marker-string assertion against rendered HTML
- **Acceptance:** live-verify in fresh Claude Code session — operator click → spinner visible within 100ms → button disabled → ~8s elapses → card removes; demo recording does not show 8s no-feedback gap on camera (load-bearing dependency for Task 3.1)

**1.3 — Health/Stats counter alignment to `Request.status == 'pending'`** (Fork B3 + Fork D resolution = D1)
- `core/api/health.py` "Pending requests" counter changed from `_requests_counts_by_folder('pending')` (rows by folder only) to `Request.status == 'pending'` SQL filter (matches inbox semantic)
- **Wiring tests:** Health/Stats partial renders pending-status count, not folder-only count; drift case (folder=pending row with status≠pending) no longer inflates counter
- **Live-verify:** counter and inbox return same number for the canonical drift case (the id=6 csvkit failed-status row from Day 10 live-verify)
- **DECISIONS:** D1 design call (counter semantic = `status='pending'`; deferred-tracking deferred to Phase 2 surface) is captured in the Day 11 close-out bundled DECISIONS entry, not in-Task-1
- **Acceptance:** Health/Stats "Pending requests" tile and inbox "X pending" header show identical numbers in all observed states, including the drift case

**Task 1 close-out:** suite regression at clean baseline (817 + new wiring tests for 1.2/1.3 = expected delta-positive, no regressions). DECISIONS bundling deferred to Day 11 close-out per Day 7 ratified bundled-entry pattern: all day-11 design decisions land as one entry, not multiple in-Task entries amended across the day.

### Task 2 — Public-release housekeeping artifacts

Three deliverables, each landing as a clean single-purpose commit:

**2.1 — `CHANGELOG.md`** (Fork C1: terse Keep-a-Changelog format)
- 0.1.0 [Unreleased] section curated from Day 1-10 SESSION snapshots
- Group by Added / Changed / Fixed / Deprecated; sub-group by domain (Catalog / Recommendation / Lifecycle / UI / Adapter / Ops disciplines)
- Pull from SESSION snapshots' "What was completed" sections at one-entry-line resolution
- Reference document, not narrative — terse imperative voice ("Added X.", not "We built X because…")
- **Acceptance:** every load-bearing 0.1.0 capability captured at one entry-line; SESSION-snapshot lineage is the authoritative source; format passes a visual scan against [keepachangelog.com](https://keepachangelog.com/en/1.1.0/)

**2.2 — `CONTRIBUTING.md`** (Fork C2: richer-with-pointers, compressed)
- ~2-3 paragraphs total, not comprehensive walkthrough
- **Pointers covering:** ops-protocol (how sessions / handoffs / DECISIONS work; `planning/concierge-operations-protocol.md`), today.md / SESSION snapshot / DECISIONS log pattern, surface-then-execute discipline, factory-only app composition, wiring-test default rule
- **Mechanics in one short paragraph:** clone, `uv sync`, run tests, open PR with description that names the surface-then-execute fork(s) the change resolves
- No comprehensive contributor-onboarding exposition — pointers, not exposition. Concierge's whole identity is its working discipline; new contributors need to understand it's load-bearing, not optional
- **Public-contact-info-confirmation rule applies:** any maintainer/contact field confirmed with operator before drafting; `hello@satietyai.io` is the only authorized public-facing email
- **Acceptance:** a new contributor reading CONTRIBUTING.md (a) understands Concierge's working discipline is load-bearing, (b) knows where to look (`planning/concierge-operations-protocol.md`, `planning/today.md`, `planning/sessions/`, `planning/decisions/DECISIONS.md`), (c) can mechanically clone-sync-test-PR

**2.3 — `.github/ISSUE_TEMPLATE/`** (Bug Report + Feature Request YAML templates)
- `bug_report.yml`: reproduction steps, expected vs. actual behavior, environment fields (Concierge version, Python version, OS, harness), logs/screenshots optional
- `feature_request.yml`: problem statement, proposed solution, alternatives considered (mirrors the surface-then-execute pattern — operator's surface should be visible in the request shape)
- **Discipline:** read-after-edit on each YAML file post-Edit; verify structural integrity before staging (YAML is structural-config — same rule as TOML / JSON edits)
- **Public-contact-info-confirmation rule:** confirm with operator before adding any contact field; default = no contact field, GitHub issue thread is the channel
- **Acceptance:** GitHub renders templates as forms when Issues opened; required fields are minimal but non-trivial; YAML structure validates (no swallowed keys / mis-nested fields)

**Task 2 close-out:** docs-only changes; suite regression unchanged.

### Task 3 — Campaign content package

Five sub-deliverables expanding the original "demo + blog draft" framing to fit the campaign-package target.

**Voice and tone calibration (load-bearing across all sub-deliverables):**
- ABOUT.md mission framing leads — "AI as the most consequential tool for individual self-development since the lever, the pulley, the industrial revolution"
- Builder-origin + teacher framing as dominant voice texture (20 years teaching + 13 months in AI; teacher identity makes the "I built this" claim land harder, not weaker)
- Genesis observation as rhetorical hook — "Agents silently use the wrong tool and never tell you why"
- "Cowork does this too" specificity is fine for LinkedIn (industry-wide-gap framing safe with this audience); use carefully on HN if pattern-matches to "competing with Anthropic" — adjust framing if so
- Lewis (legal name) per Day 9 naming convention — applies to all Task 3 public-facing content
- Public-contact-info-confirmation rule: `hello@satietyai.io` is the only authorized public-facing contact

---

**3.1 — Demo recording (60-90s, operator-visible, on-camera)**
- Lewis on camera; dashboard visible on screen; Claude Code agent visible alongside; the third-voice moment lands live (operator + agent + Concierge)
- OBS Studio drives capture (already configured for the broader SatietyAI campaign); visual continuity with broader campaign production matters
- **Two cuts:**
  - **Vertical/short cut for LinkedIn + YouTube Shorts** (60-75s, 9:16 vertical aspect)
  - **Horizontal cut for longer YouTube post** (60-90s, 16:9 horizontal aspect)
- **Pre-recording dependencies:** Task 1.2 hx-indicator polish must land first (so demo doesn't show the 8s no-feedback gap on camera); fresh Claude Code session for SSE trigger; operator runs through script once before final take
- **Demo arc:** agent files a tool request → Concierge surfaces alternative + reasoning in the dialogue → operator approves on camera → tool loads + agent uses it → counter updates in real time
- **Storage:** video files NOT committed to repo (binary; large); paths to recorded master files documented in Day 11 SESSION close-out
- **Acceptance:** both cuts exported; visual/audio quality matches operator's broader campaign production standard; the third-voice moment is unambiguous on camera

**3.2 — LinkedIn launch post draft** (~400-600 words)
- **Stored at:** `planning/scratch/day-11-launch-content/linkedin.md`
- Builder-origin + teacher framing as lead voice (20 years teaching + 13 months in AI on-ramp via Cowork → OpenClaw → Concierge lineage)
- Mission-aligned to SatietyAI per ABOUT.md anchor
- Genesis observation as opening hook
- Technical depth in lower half — what Concierge is, how it works, why it generalizes (third voice; multi-tier identity-aware substrate)
- "Cowork does this too" specificity OK for LinkedIn audience
- Closing: pointer to repo + `hello@satietyai.io`
- Demo cut embedded (vertical cut from 3.1)
- **Acceptance:** post is operator-ready (operator can copy/paste into LinkedIn with no further editing); voice is builder-origin-led; mission framing is load-bearing; demo cut embedded inline

**3.3 — YouTube launch post draft**
- **Stored at:** `planning/scratch/day-11-launch-content/youtube.md`
- Video-first format; description copy with key timestamps marked (matched to demo arc beats)
- Shorter than LinkedIn version (~150-300 words description); demo-centric
- Hook in first 15 seconds aligns to LinkedIn hook (genesis observation)
- Description includes: pointer to repo, ABOUT.md, `hello@satietyai.io`
- **Acceptance:** post is operator-ready; description is timestamp-anchored to demo arc; copy is YouTube-native (not LinkedIn-cross-pasted)

**3.4 — HackerNews submission draft** (unconditionally in Day 11 scope)
- **Stored at:** `planning/scratch/day-11-launch-content/hn.md`
- Day 11 produces the draft. **Whether and when to submit to HN is a separate campaign-distribution decision (operator + agent crew at campaign level), not a Day 11 execution-time decision.** Cost of producing during Task 3 is minimal (drafted alongside the LinkedIn/YouTube drafts in the integrated content package); cost of producing later cold-drafted is much higher.
- Shorter (~200-400 words), technical-heavy, vision-framing as hook (third voice + multi-tier identity-aware substrate from CLAUDE.md vision section)
- "Cowork does this too" specificity used carefully — HN may pattern-match to "competing with Anthropic"; adjust framing toward gap-in-tooling rather than vendor-comparison if the read suggests that risk
- Different audience from LinkedIn — leans into genesis observation + architecture, less into builder-origin
- Includes title + body + repo URL with placeholder for Day 12 fill-in
- **Acceptance:** operator-ready submission with title + body + repo URL placeholder

**3.5 — Content calendar pointers** (3-5 seeds for agent crew distribution)
- **Stored at:** `planning/scratch/day-11-launch-content/content-seeds.md`
- Concept seeds for the agent crew to develop into subsequent campaign beats
- **Each seed: 2-3 sentences covering angle + target audience + which campaign beat it serves**
- **Default seeds (refined at execution):**
  - "Why agents don't tell you about tools" (LinkedIn / YouTube; tool-awareness gap; education beat)
  - "The third voice in AI dialogue" (LinkedIn / Twitter; vision-driven; concept beat)
  - "Building tool awareness for your own agents" (LinkedIn dev audience / YouTube tutorial; how-to; technical beat)
  - "The teaching practice behind the infrastructure" (LinkedIn / cross-post; SatietyAI mission cross-promotion; origin beat)
  - Fifth seed open for execution-time addition
- NOT full posts — seeds for downstream development by the agent crew
- **Acceptance:** 3-5 seeds documented; each seed has angle / audience / beat fields; format consumable by the agent crew

**Task 3 close-out:**
- Single bundled commit at end of Task 3: `docs(launch): Day 11 campaign content package draft` (covers all written drafts at `planning/scratch/day-11-launch-content/`)
- Demo video master files: paths documented in Day 11 SESSION close-out, NOT committed to repo
- Operator review of content drafts before any external publication (Day 11 produces drafts; publish timing is operator-driven across the campaign rollout)

## End-of-day deliverable

- Three Day-10 forward-carry polish items landed in production code (`uv run` prefix in README; hx-indicator on action buttons; Health/Stats counter aligned to `status='pending'`)
- CHANGELOG.md + CONTRIBUTING.md + `.github/ISSUE_TEMPLATE/` landed for the public repo
- Campaign content package drafted: demo recording with two cuts (vertical + horizontal), LinkedIn / YouTube / HN drafts, 3-5 content calendar seeds for the agent crew
- Suite at clean baseline
- **DECISIONS bundled entry `[2026-05-02 Day 11]` written at Day 11 close-out** per Day 7 ratified bundled-entry pattern. Covers all day-11 design decisions: D1 counter semantic (`status='pending'`; deferred-tracking deferred to Phase 2 surface); CHANGELOG voice (terse Keep-a-Changelog); CONTRIBUTING shape (richer-with-pointers compressed; ops-protocol + today.md/SESSION/DECISIONS pattern + surface-then-execute as load-bearing pointers); issue template structure (Bug Report + Feature Request YAML; surface-then-execute mirrored in feature-request shape); content package architecture (two-variant LinkedIn/YouTube split + HN draft unconditionally produced with submission decision separated to campaign level + content calendar seeds as agent-crew distribution surface).
- Day 11 SESSION close-out snapshot at `planning/sessions/SESSION-2026-05-02-01.md` (logical-day form per established day-shift pattern)
- today.md updated to Day 12 placeholder (final review + GitHub push)

## Checkpoint criteria

- [ ] README install + canonical-launch sections use `uv run` prefix; clone-into-fresh-WSL-shell verifies launch command boots dashboard
- [ ] hx-indicator landed on Approve/Deny/Defer buttons; live-verify shows in-flight feedback within 100ms; demo recording does not show 8s no-feedback gap on camera
- [ ] Health/Stats "Pending requests" counter aligned to `Request.status == 'pending'`; matches inbox count in canonical drift case
- [ ] CHANGELOG.md exists at project root, terse Keep-a-Changelog format, 0.1.0 [Unreleased] section curated from SESSION snapshots
- [ ] CONTRIBUTING.md exists at project root, richer-with-pointers compressed shape (~2-3 paragraphs); references ops-protocol + today.md/SESSION/DECISIONS pattern + surface-then-execute
- [ ] `.github/ISSUE_TEMPLATE/bug_report.yml` + `feature_request.yml` exist; YAML structure verified read-after-edit
- [ ] Demo recording: two cuts exported (vertical for LinkedIn/Shorts; horizontal for YouTube); operator confirms quality; master file paths documented in Day 11 SESSION close-out
- [ ] LinkedIn launch post draft at `planning/scratch/day-11-launch-content/linkedin.md`; ~400-600 words; builder-origin lead; genesis-observation hook; mission framing; demo cut embedded
- [ ] YouTube launch post draft at `planning/scratch/day-11-launch-content/youtube.md`; ~150-300 words; description timestamp-anchored
- [ ] HN submission draft at `planning/scratch/day-11-launch-content/hn.md` (unconditional)
- [ ] Content calendar pointers at `planning/scratch/day-11-launch-content/content-seeds.md`; 3-5 seeds with angle / audience / beat fields
- [ ] Suite regression at clean baseline post Task 1
- [ ] DECISIONS bundled entry `[2026-05-02 Day 11]` written at Day 11 close-out covering all day-11 design decisions (D1 counter semantic, CHANGELOG voice, CONTRIBUTING shape, issue template structure, content package architecture)
- [ ] Day 11 SESSION snapshot at `planning/sessions/SESSION-2026-05-02-01.md` (logical-day form per established day-shift pattern)
- [ ] today.md updated to Day 12 placeholder (final review + GitHub push)

## Session opener

Paste this verbatim into a fresh Claude Code session to kick off Day 11 execution sessions:

---

> Read in order, then confirm understanding before acting:
>
> 1. `CLAUDE.md` (project root — pruned in Day 9 to definitive voice; 92 lines)
> 2. `planning/concierge-operations-protocol.md` ← three ratified disciplines: "Decision-edit pattern", "Wiring-test discipline", and "Live verify discipline"
> 3. `planning/sessions/SESSION-2026-05-01-01.md` ← Day 10 close-out (seven commits + four forward-carries: uv run prefix, hx-indicator UX gap, approve-action 8s perf question, Health/Stats counter drift; four screenshots at `planning/scratch/day-10-screenshots/`)
> 4. `planning/today.md` ← this file (Day 11 ratified plan: launch artifacts day with Task 3 expanded to campaign content package per active SatietyAI brand-building campaign)
> 5. `planning/decisions/DECISIONS.md` — tail; especially `[2026-05-01 Day 10]` UI architecture entry
>
> Today is Day 11 — launch artifacts day. **Day 11 is a beat in an active multi-week SatietyAI brand-building campaign**, not a one-shot launch. Three-task structure:
>
> - **Task 1** = Day-10 forward-carry polish (README `uv run` prefix; hx-indicator on Approve/Deny/Defer buttons; Health/Stats counter alignment to `Request.status == 'pending'` per Fork D1)
> - **Task 2** = public-release housekeeping (CHANGELOG terse Keep-a-Changelog; CONTRIBUTING richer-with-pointers compressed; `.github/ISSUE_TEMPLATE/` Bug Report + Feature Request)
> - **Task 3** = campaign content package — demo recording (60-90s, on-camera, two cuts vertical + horizontal); LinkedIn launch post draft (~400-600 words); YouTube launch post draft (~150-300 words); HackerNews submission draft (~200-400 words; submission timing is a separate campaign-level decision); 3-5 content calendar seeds for the agent crew
>
> Effort: max throughout. Public-facing day; voice + content quality matter.
>
> **Voice and tone calibration for Task 3 (load-bearing):**
> - ABOUT.md mission framing leads — Concierge is infrastructure for the same mission as SatietyAI's teaching
> - Builder-origin + teacher framing is the dominant voice texture (20 years teaching + 13 months in AI)
> - Genesis observation ("Agents silently use the wrong tool and never tell you why") is the rhetorical hook
> - "Cowork does this too" specificity — fine for LinkedIn; use carefully on HN (adjust toward gap-in-tooling framing if pattern-match-to-vendor-comparison risk surfaces)
> - Lewis (legal name) per Day 9 naming convention; `hello@satietyai.io` is the only authorized public-facing contact
>
> **DECISIONS bundling:** all day-11 design decisions land as one bundled entry `[2026-05-02 Day 11]` at Day 11 close-out, not in-Task. Per Day 7 ratified bundled-entry pattern. Covers D1 counter semantic, CHANGELOG voice, CONTRIBUTING shape, issue template structure, and content package architecture.
>
> **Discipline carry-forward (durable constraints from Days 2-10):**
> - Test-fails-first for any new test landing on a fix
> - Wiring tests assert client-observable contracts — default rule
> - Live shakedowns are fresh-session-only for user-experience claims
> - Surface-then-execute for architectural decisions
> - Mid-stream re-surface for forks
> - In-place DECISIONS edits OK for current-day entries
> - Report between steps; proceed unless intervened
> - Time-box discipline on ambiguous-scope investigations (candidate)
> - Clean-baseline regression signal with N≥5 flake-rate characterization for intermittent failures
> - Single-venv discipline (candidate, Day 8): `.venv` is canonical when uv is the dependency manager
> - Lewis/Lewie naming convention (candidate, Day 9): Lewis (legal) public; Lewie (operational) internal — Lewis applies for all Task 3 public content
> - Read-after-edit for structural config files (candidate, Day 9): edit-success ≠ semantic correctness; applies to README markdown structure (Task 1.1) and `.github/ISSUE_TEMPLATE/*.yml` (Task 2.3)
> - Public-contact-info-confirmation rule (Day 9, codified durably via feedback memory): never infer email/phone/handle/real-name from git/env/auto-memory for public artifacts; `hello@satietyai.io` is the only authorized public-facing email
> - Factory-only app composition (Day 10): both `core.app` and `ui.app` are factory-only; canonical launch via `--factory` flag
>
> Do not begin code on tasks until you've surfaced the task-level approach and I've confirmed alignment. Surface-then-execute applies at task entry.

---

*48h shakedown clock continues running cleanly through Day 10 — UI changes touch dashboard surface (templates, static assets, partial-render endpoints, factory-only refactor); Day 11 changes touch UI partial (action-button hx-indicator), one core API endpoint (Health/Stats counter SQL filter), README, CHANGELOG, CONTRIBUTING, issue templates, and content drafts at `planning/scratch/`. Substrate paths (recommend / SSE wire format / lifecycle store) untouched. Soak observations should land in the Day 11 SESSION snapshot.*

*Forward-carry items not in Day 11 scope:*

- *Repository URL fill-in for `pyproject.toml [project.urls]` — Day 12 (once GitHub URL is known)*
- *`<repo-url>` placeholder fill-in for README clone command — Day 12*
- *Final GitHub push — Day 12*
- *Approve action 8s performance investigation (Day 10) — future-day priority*
- *Token-weight tracker (Day 10 alignment forward-carry) — Phase 2 design surface*
- *`GET /stats/top-tools` event-type filter cutover (Day 10) — when used-event-wiring lands*
- *Phase 2 UI sections (Lifecycle Activity / Wishlist Patterns / Cross-Agent Map / Settings) — not v0.1*
- *Whether Fork 1 / Fork 4 deserve formal DECISIONS entries post-hoc (Fix Day 3)*
- *Install-path auto-transition vs scanner-owned state changes (Fix Day 3 Question 2)*
- *Skills-specific "used" detection signal sources (Fix Day 3 Question 3 / Fix Day 4 Fork H)*
- *Loader-emit wiring scheduling (Fix Day 4 Open Question 2)*
- *Catalog-slug aliasing convention (Fix Day 5)*
- *Venv-corruption-events Appendix as ops-protocol section (Day 7 Appendix C — candidate)*
- *Time-box discipline on ambiguous-scope investigations (Day 7 Appendix E — candidate)*
- *Single-venv discipline (Day 8 Appendix C — candidate)*
- *Clean-baseline-flake-rate refinement (Day 8 Appendix D — candidate)*
- *Lewis/Lewie naming convention (Day 9 — candidate)*
- *Read-after-edit discipline for structural config files (Day 9 — candidate; multiple data points logged on Day 10)*
- *Vision-section "verbatim" preservation refinement (Day 9 — candidate)*
- *Public-contact-info-confirmation rule (Day 9 — codified via memory; awaits second data point for ops-protocol ratification)*
- *Flake-rate P2 investigation (Day 8 Appendix B; 1/5 = 20%) — pushed past Day 11 unless headroom*
