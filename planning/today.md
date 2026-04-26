# Today — 2026-05-01 (Day 10 — UI day)

*Opens on: `SESSION-2026-04-30-01.md` (Day 9 close-out — six commits landing public-release scaffolding: pyproject httpx classification fix `dc4bf90`, substantive README rewrite `36cd171`, MIT LICENSE `0caee12`, pyproject metadata with PEP 639 license + authors + Homepage URL `60a6c96`, ABOUT.md builder bio `87b4c61`, CLAUDE.md prune (49% line reduction; 180 → 92 lines) `4c3fdf8`. DECISIONS `[2026-04-30 Day 9]` bundled entry covers LICENSE + attribution + pyproject metadata + email convention. Four forward-carry candidate-patterns flagged: Lewis/Lewie naming convention, read-after-edit discipline for structural config files, Vision-section "verbatim" preservation refinement, public-contact-info-confirmation rule.*

*Day 10 alignment session resolved all primary forks (scope shape, stack, app composition) plus two real-check refinements (designed empty-state Tool Registry; tokens-saved feature dropped from v0.1) plus two execution adjustments (factory-only app launch, SSE live-verify specifics nailed down). Operator decisions ratified into this plan.*

## Governing framing

UI day. Build the operator-side observability surface to **v0.1-quality**: three sections (Tool Registry with designed empty state, Pending Requests Inbox with SSE live updates, Health/Stats bar with reduced surface) on FastAPI + Jinja2 + HTMX + Pico.css vendored. Composition pattern: `ui/app.py` wraps `core.create_app()` so headless deployments stay UI-free.

**No time-box, no scope-cap on Day 10.** Build the right thing, not the shortest version. If a task takes longer than estimated, take the time. Surface re-scope only on a fork or genuine architectural surprise — not on normal "task running long." Live-verify is non-negotiable.

## Operator decisions ratified at alignment

1. **Scope shape: (A) full-fidelity three sections** per blueprint v2 §UI in detail § Hackathon-week scope. Tool Registry browsable + filterable + searchable; Pending Inbox with approve/deny/defer + comment field + SSE live updates; Health/Stats bar with reduced surface (see #4).
2. **Stack: Jinja2 + HTMX + Pico.css, vendored.** `jinja2` lands in main `[project] dependencies` (Day 9 httpx-classification logic — runtime deps belong in main). HTMX + Pico.css vendored under `ui/static/vendor/` for offline-friendly + reproducible-build.
3. **App composition: `ui/app.py` wraps `core.create_app()`.** Cleaner separation chosen explicitly: "folks who don't want the UI shouldn't have to have the UI." `core/` stays UI-free; no Jinja2 imports, no template rendering, no `/ui` routes in the core app. Headless deployments instantiate `core.create_app()` directly; dashboard deployments instantiate `ui.create_app()`. **Factory-only — `ui/app.py` exposes the `create_app()` factory and nothing else; no module-level `app` instantiation, to avoid heavyweight side-effects-on-import (DB connections, scanner spin-up, full service surface) contaminating test infrastructure and introspection imports.**
4. **Tokens-saved counter dropped from v0.1 entirely.** No endpoint, no UI element, no placeholder. "Saved" requires a counterfactual baseline that isn't measurable without speculative assumptions; per-task / per-session / per-boot windows each produce a different-meaning number. Health/Stats bar reduces to: service health + what's loaded + scanner heartbeat + top-3 most-used tools.
5. **Top-3 most-used tools: server-side aggregation via new `core/api/stats.py` router** with `GET /stats/top-tools`. Aggregates from request history (real recorded data).
6. **Tool Registry empty state: designed, not accidental.** Friendly copy explaining the state when catalog is empty. No seed data ships with the package; empty installs ship empty.
7. **Pending Inbox empty state: same designed treatment** when zero pending requests. Empty states are designed states everywhere they appear; consistent application across both sections, not narrow scope.
8. **Layout: single-page dashboard** (header strip + three stacked panels). One screenshot covers everything.
9. **SSE for Pending Inbox new-request highlight; 5-10s HTMX polling fallback** for Health/Stats counters (no SSE event for those today).
10. **Catalog display: cards-in-pack-groups** (pack-as-section-header, sub-tools as cards inside).
11. **Tests: FastAPI `TestClient` + HTML marker-string assertions for wiring.** Live-verify covers UX claims. No Playwright.
12. **Token-weight tracker forward-carried** as Phase 2 / future-consideration: measuring the actual context-cost of each tool/MCP/skill at load time gives operators real "is this worth keeping loaded?" information — different feature with different design surface than tokens-saved. Logged in Day 10 SESSION forward-carry, not Day 10 work.

## Day 10 — UI day

**Primary goal:** Build the operator-facing dashboard at `ui/app.py` with three v0.1-quality sections backed by the existing core API surface plus one small new endpoint (`GET /stats/top-tools`). Verified via wiring tests + a fresh-`uvicorn` browser walkthrough that captures three screenshots for Day 11 demo recording inputs.

## Tasks

### Task 0 — Stack scaffolding + composition shim

**Deliverable:** A working `ui.create_app()` factory that wraps `core.create_app()` and serves a hello-page; `core.create_app()` still spawns headlessly with no UI mounted.

**Steps:**

1. Add `jinja2>=3.1` to main `[project] dependencies` in `pyproject.toml`. **Read-after-edit** per Day 9 candidate-pattern (the dependencies array got swallowed by a TOML structural-edit error on Day 9 — verify the file structure after the edit before running `uv sync`). `uv sync` and verify the lock updates cleanly.
2. Vendor HTMX (`htmx.min.js`) and Pico.css (`pico.min.css`) under `ui/static/vendor/`. Include version-pinned files; add `ui/static/vendor/README.md` documenting version + source URL + vendoring rationale (offline-friendly + reproducible-build).
3. Create `ui/templates/` with a placeholder `index.html` (Jinja-rendered hello-page; replaced in Task 4).
4. Create `ui/router.py`: `APIRouter` exposing `GET /` rendering `index.html` via `Jinja2Templates`; `StaticFiles` mount for `ui/static/` at `/static`.
5. Create `ui/app.py`: `create_app()` factory calls `core.app.create_app()`, includes the UI router, mounts static files, returns the augmented app. **Factory-only — do not expose `app = create_app()` at module level.** Heavyweight side-effects-on-import (DB connections, scanner spin-up, full service surface) are the bug class to avoid; module-level instantiation contaminates test infrastructure and any introspection import. The canonical launch command is `uvicorn ui.app:create_app --factory`.
6. **Wiring test:** TestClient against `ui.create_app()` returns 200 on `GET /` with marker string from the placeholder template; `GET /static/vendor/htmx.min.js` resolves.
7. **Wiring test (negative):** TestClient against `core.create_app()` directly returns 404 on `GET /` — proves the headless deployment surface stays clean.
8. **Wiring test (factory-only contract):** assert `ui.app` module exposes `create_app` but does NOT expose a module-level `app` attribute. Cheap test; locks the contract against accidental retrofit.

**Surface checkpoints:** none expected. If `uv sync` produces any unexpected dependency-tree shifts, mid-stream re-surface.

### Task 1 — Health/Stats bar + `GET /stats/top-tools`

**Deliverable:** Health/Stats bar partial rendering four pieces (service health, what's loaded, scanner heartbeat, top-3 most-used tools), polled every 10s via HTMX. New `core/api/stats.py` router with `GET /stats/top-tools` aggregating from request history.

**Steps:**

1. Audit data sources: confirm `/health` payload covers service health + what's-loaded counters + scanner heartbeat. (Verified at alignment: yes — `core/api/health.py:65` returns `counters` + `catalog` + `scanner` fields.)
2. **[Surface checkpoint]** Investigate which DB table holds the "most-used" signal — request rows, `tool_usage_events` (telemetry), or recommend log. Pick the most-stable source and **surface for operator alignment** before coding. Lean: telemetry `tool_usage_events` if it has the right shape; falls back to request-history rows otherwise.
3. Create `core/api/stats.py` with `GET /stats/top-tools` aggregating the picked source; returns top-3 by usage count. Pydantic response model.
4. Wire the stats router into `core/app.py` `create_app()`.
5. **Wiring test for the endpoint:** TestClient + DB fixtures seed N usage rows; assert top-3 ordering correct.
6. Create `ui/templates/partials/health_bar.html` Jinja partial.
7. Add `GET /partials/health-bar` to `ui/router.py` rendering the partial against fresh data (composes `/health` + `/stats/top-tools` server-side via direct service calls, not self-HTTP-loop).
8. Wire HTMX polling: `hx-get="/partials/health-bar" hx-trigger="every 10s" hx-swap="outerHTML"` on the health-bar element.
9. **Wiring test for the partial render:** TestClient + marker strings in HTML.

**Surface checkpoints:** Step 2's data-source pick is the load-bearing surface. Surface before picking.

### Task 2 — Tool Registry section + designed empty state

**Deliverable:** Tool Registry partial rendering catalog as cards-in-pack-groups with filter form (lifecycle state, tool type, category, name search) and designed empty state for empty catalog.

**Steps:**

1. **[Surface checkpoint]** Audit `/tools` filter coverage: existing query params at `core/api/tools.py:38` are `pack_id`, `pack_slug`, `is_active`, `is_in_manifest`, `dormant`, `category`, `tool_type`, `slug`. Free-text name search is an API gap (`slug` is exact-match only). Surface decision: add `name_q` substring filter to `/tools` server-side, or do client-side filter. Lean: server-side `name_q` (cleaner UX; small change). **Surface before deciding.**
2. If lean accepted: add `name_q: Optional[str] = Query(None)` to `core/api/tools.py:list_tools` with case-insensitive substring match on `Tool.name`. Wiring test for the new filter.
3. Create `ui/templates/partials/tool_registry.html`. Layout: filter form at top + iterate packs as `<section>`s with `<h2>` pack name + nested cards for sub-tools. Each card shows: name, lifecycle state badge, tool type, install method, last-used (if available), pack slug.
4. Create `ui/templates/partials/tool_registry_empty.html` for the designed empty state. Copy:

   > No tools catalogued yet. Tools will appear here as Concierge discovers and approves them. The agent will surface tool requests when it hits a capability gap; you'll see those in the Pending Requests inbox.

   Adjust copy for voice consistency once the rest of the dashboard lands. Include a one-line hint about how to trigger discovery (agent-side request) so the empty state is informative, not just decorative.
5. Add `GET /partials/tool-registry` to `ui/router.py` accepting filter query params, calling the catalog services directly (not self-HTTP), branching to the empty-state partial if zero results.
6. Filter form HTMX-wired: `hx-get="/partials/tool-registry"`, `hx-target="#tool-registry"`, `hx-swap="outerHTML"` on form change.
7. **Wiring test for non-empty render:** TestClient + DB fixtures with N tools across M packs; assert pack groupings + tool-card presence + filter behavior.
8. **Wiring test for empty-state render:** TestClient against fresh DB (no tools); assert designed empty-state copy renders.

**Surface checkpoints:** Step 1's `name_q`-filter decision. Surface before adding the query param.

### Task 3 — Pending Requests Inbox section + SSE live updates

**Deliverable:** Pending Inbox partial rendering pending requests as cards with Approve / Deny / Defer buttons + optional comment field; SSE-driven new-request highlight when a fresh request fires; designed empty state for zero pending.

**Steps:**

1. Audit `GET /requests/pending` response and `POST /requests/{id}/{action}` action contract (`core/api/requests.py:94` and `core/api/requests.py:119`). Verified at alignment.
2. Create `ui/templates/partials/pending_inbox.html`. Layout: cards with structured markdown nicely formatted; per-card form with comment textarea + three action buttons.
3. Add `GET /partials/pending-inbox` to `ui/router.py` rendering the partial against `/requests/pending` data (or the underlying service directly).
4. Wire action buttons: `hx-post="/requests/{id}/approve|deny|defer"` with the comment textarea included; `hx-target` updates the card to its post-action state.
5. Wire SSE: `hx-sse="connect:/ui/events"` at the inbox element; `hx-swap-oob="afterbegin:#inbox-cards"` on `new_request` events to append fresh cards. (Wire format already JSON-serialized at `core/api/events.py:87-89` per Day 5 fix.)
6. Designed empty state when no pending requests:

   > No pending tool requests. When the agent hits a capability gap, requests will appear here for your review.

7. **Wiring test for non-empty render + action POST:** TestClient + DB fixtures with N pending; POST approve, assert side effect + render update.
8. **Wiring test for SSE event handling:** publish a `new_request` event through the broker; assert the SSE response contains the expected `event:` + `data:` lines (JSON-parsed) — wiring-test discipline applied to SSE wire format per the Day 5 four-data-point narrative.
9. **Wiring test for empty-state render:** assert designed empty-state copy when zero pending.

**Surface checkpoints:** SSE + HTMX `hx-sse` consumption is wiring-discipline-critical. If `hx-swap-oob` fires multiple times or duplicates cards, surface immediately.

### Task 4 — Index page composition + CSS polish

**Deliverable:** `ui/templates/index.html` composing all three sections in single-page layout with header strip + stacked panels. Light CSS polish above Pico.css base for layout density and operator-friendly spacing.

**Steps:**

1. Replace the Task 0 placeholder `ui/templates/index.html`. Header strip at top includes the Health/Stats bar partial + service title + version. Three stacked panels follow: Tool Registry, Pending Inbox.
2. Create `ui/static/css/concierge.css` for layout tweaks: max-width container, panel spacing, card grid, badge styling for lifecycle states.
3. Wire HTMX, Pico.css, and `concierge.css` `<link>`/`<script>` tags in `<head>`.
4. **Wiring test for full-page render:** TestClient + DB fixtures with non-trivial state; assert all three section markers present + Pico.css link + HTMX script tag.

**Surface checkpoints:** none expected; CSS polish is iterative.

### Task 5 — Live-verify discipline (non-negotiable)

**Deliverable:** Fresh-`uvicorn` browser walkthrough validates the dashboard end-to-end. Three screenshots captured for Day 11 demo recording inputs. Operator-side validation that the dashboard feels like a real operator surface.

**Steps:**

1. Fresh terminal, clean `.venv`. `uv sync` to ensure deps current.
2. Launch: `uvicorn ui.app:create_app --factory --reload --port 8000` per Task 0 Step 5's factory-only decision.
3. Open `http://localhost:8000` in browser.
4. Walk through:
   - **Health/Stats bar** at top: service health + what's-loaded + scanner heartbeat + top-3 tools render. Wait 10s, observe polling refresh.
   - **Tool Registry**: cards-in-pack-groups render. Apply each filter (lifecycle state, tool type, category, name search) and confirm partial-only refresh. If catalog is empty, confirm designed empty state renders.
   - **Pending Inbox**: cards render with three action buttons + comment field. Click Approve on one card and confirm state transition.
   - **SSE live-verify (specifics):**
     - **(a) Trigger session shape:** fresh Claude Code session with Concierge MCP registered against the development install (NOT the build session). Fresh session gives a production-shaped trigger, not contaminated by build-conversation context.
     - **(b) Trigger prompt:** ask for a tool/skill plausibly missing from a fresh-clone catalog — e.g. *"I need to do OCR on a scanned PDF, what's available?"* if `ocrmypdf` or similar isn't catalogued. Adjust based on actual catalog state at execution; the requirement is that `concierge_request_tool` fires against a non-catalogued capability so a new pending request lands in `outbox/tool-requests/pending/`.
     - **(c) Fallback validation:** if the SSE-driven append doesn't visibly land in the browser within ~5 seconds, refresh `GET /partials/pending-inbox` directly (or hard-reload the page) and confirm the new request is in the rendered partial. This distinguishes three cases:
       - polling shows the request, SSE didn't fire → **frontend SSE bug**, surface immediately
       - polling doesn't show the request → **backend bug** (request didn't land or didn't reach the inbox query path), surface immediately
       - both succeed → **SSE working as designed**; live-verify passes
5. Capture three screenshots:
   - **Screenshot 1:** Full dashboard overview (header + three sections in single-page layout) → `01-dashboard-overview.png`
   - **Screenshot 2:** Tool Registry with cards-in-pack-groups + filter form → `02-tool-registry.png`
   - **Screenshot 3:** Pending Inbox with at least one card showing approve/deny/defer + comment field → `03-pending-inbox.png`
6. Save screenshots to `planning/scratch/day-10-screenshots/`.
7. Capture browser walkthrough notes in the SESSION snapshot's Live-Verify Appendix: any observed UX issues, polish needed, surprises, plus the SSE-vs-polling outcome from Step 4(c).

**Surface checkpoints:** any UX issue surfaced during walkthrough that materially degrades the v0.1 operator experience surfaces immediately. SSE-vs-polling discrepancy from Step 4(c) (frontend bug or backend bug) surfaces immediately.

## DECISIONS expectations

One bundled DECISIONS.md entry expected at end of Day 10 per the Day 7 ratified decision-edit pattern:

**`[2026-05-01 Day 10] — UI architecture + v0.1 design-surface decisions`**

Covers:
- App composition: `ui/app.py` wraps `core.create_app()` (separation of concerns; headless deployments stay UI-free); **factory-only — no module-level `app` instantiation, to avoid heavyweight side-effects-on-import**
- Stack: Jinja2 + HTMX + Pico.css, vendored under `ui/static/vendor/`
- Layout: single-page dashboard (header strip + 3 stacked panels)
- Empty-state philosophy: designed empty states for empty installs (no seed data ships with package); applies to Tool Registry and Pending Inbox
- Tokens-saved feature dropped from v0.1 (counterfactual-baseline + measurement-window concerns); token-weight-tracker forward-carried as Phase 2 idea
- `GET /stats/top-tools` server-side aggregation from request history (data source picked at execution Task 1 Step 2 surface)
- SSE for inbox new-request highlight; 5-10s HTMX polling for non-event-driven counters
- Tool Registry: cards-in-pack-groups display, optional `name_q` substring filter on `/tools` (decided at execution Task 2 Step 1 surface)

If any single decision becomes large enough to warrant standalone treatment during execution, surface for operator alignment on bundled-vs-split.

## End-of-day deliverable

- Working dashboard at `localhost:8000` rendering all three sections against current catalog/lifecycle state
- `ui/app.py:create_app()` factory wrapping `core.create_app()`, mountable independent of the core service; no module-level `app` instantiation
- New endpoint: `GET /stats/top-tools` aggregating from request history; integrated into Health/Stats bar
- Vendored HTMX + Pico.css under `ui/static/vendor/` with version + source documented
- Wiring tests covering every new endpoint + partial render + filter + action POST + SSE wire-format consumption + factory-only contract
- Three screenshots in `planning/scratch/day-10-screenshots/` for Day 11 demo-recording inputs
- DECISIONS.md updated with `[2026-05-01 Day 10]` bundled entry
- SESSION snapshot at `planning/sessions/SESSION-2026-05-01-NN.md` (NN = session number) per protocol; Live-Verify Appendix capturing browser walkthrough notes + SSE-vs-polling outcome; forward-carry section logging the token-weight-tracker idea
- `planning/today.md` updated to Day 11 plan (launch artifacts day)

## Checkpoint criteria

- [ ] `ui/app.py:create_app()` exists; `ui.create_app()` returns FastAPI app with UI mounted
- [ ] `ui/app.py` exposes ONLY the `create_app()` factory; no module-level `app` instantiation (verified by wiring test)
- [ ] `core.create_app()` continues working headlessly; `GET /` returns 404 (no UI route)
- [ ] `jinja2` declared in main `[project] dependencies` (not dev extras); read-after-edit confirmed
- [ ] HTMX + Pico.css vendored under `ui/static/vendor/` with version + source documented
- [ ] `GET /stats/top-tools` returns aggregated top-3 from request history; wiring test passes
- [ ] Tool Registry renders cards-in-pack-groups for non-empty catalog
- [ ] Tool Registry renders designed empty state when catalog is empty
- [ ] Tool Registry filter form works (HTMX-driven, refreshes only the partial; lifecycle / tool-type / category / name_q)
- [ ] Pending Inbox cards render with approve/deny/defer buttons + comment field
- [ ] Approve/deny/defer hits existing `POST /requests/{id}/{action}` endpoints; UI updates accordingly
- [ ] SSE-driven new-request append works against `/ui/events`
- [ ] Pending Inbox renders designed empty state when zero pending
- [ ] Health/Stats bar shows service health + what's-loaded + scanner heartbeat + top-3 tools
- [ ] Health/Stats bar polls every 10s via HTMX `hx-trigger`
- [ ] Index page composes all three sections in single-page layout with light CSS polish
- [ ] Wiring tests pass for every new endpoint, partial render, filter, action POST, SSE wire-format consumption, factory-only contract
- [ ] Live-verify completed: fresh `uvicorn` (factory-form launch), browser walkthrough, three sections validated, SSE-vs-polling outcome resolved
- [ ] Three screenshots captured at `planning/scratch/day-10-screenshots/`
- [ ] DECISIONS.md updated with `[2026-05-01 Day 10]` bundled entry
- [ ] Day 10 SESSION snapshot written
- [ ] today.md updated to Day 11 plan

## What Day 10 is NOT

Explicitly excluded from Day 10 scope:

- **CHANGELOG.md / CONTRIBUTING.md / `.github/ISSUE_TEMPLATE/`** — Day 11 launch artifacts.
- **Demo recording (60-90s)** — Day 11. Day 10 produces the screenshot inputs; Day 11 records.
- **Blog post / launch thread draft** — Day 11.
- **Final review + push to GitHub** — Day 12.
- **Repository URL fill-in** for `pyproject.toml` `[project.urls]` — Day 12 (once GitHub URL is known).
- **`<repo-url>` placeholder fill-in** for README clone command — Day 12.
- **Tokens-saved counter** — explicitly dropped from v0.1 per operator alignment (counterfactual-baseline + measurement-window concerns; see DECISIONS expectations). Day 10 SESSION forward-carry will note token-weight tracker as separate Phase 2 idea (measuring actual context-cost of tools/MCPs/skills at load time gives operators real "is this worth keeping loaded?" information; different feature with different design surface than tokens-saved).
- **Phase 2 UI sections** (Lifecycle Activity / Wishlist Patterns / Cross-Agent Map / Settings) — out of v0.1 scope per blueprint v2 §Post-hackathon UI sections (Phase 2). Sketched-as-templates-for-later not part of Day 10.
- **Browser-level Playwright smoke tests** — out of scope; FastAPI `TestClient` + marker-string assertions cover wiring, live-verify covers UX claims.
- **Flake-rate P2 investigation** (Day 8 Appendix B; 1/5 = 20%) — Day 10 has no headroom given full-fidelity scope.
- **Seed data for empty installs** — empty installs ship empty; designed empty-state views handle it (Real Check 1 + extension to Pending Inbox).
- **Module-level `app = create_app()`** in `ui/app.py` — factory-only per Task 0 Step 5. The canonical launch command is `uvicorn ui.app:create_app --factory`.

## Session opener

Paste this verbatim into a fresh Claude Code session to kick off Day 10 execution. Each execution session begins from this opener; if a session ends mid-task, the next session reads the updated `planning/today.md` and the most recent SESSION snapshot before continuing.

---

> Read in order, then confirm understanding before acting:
>
> 1. `CLAUDE.md` (project root — pruned in Day 9 to definitive voice; 92 lines)
> 2. `planning/concierge-operations-protocol.md` ← three ratified disciplines: "Decision-edit pattern", "Wiring-test discipline", and "Live verify discipline"
> 3. `planning/sessions/SESSION-2026-04-30-01.md` ← Day 9 close-out covering six commits + four forward-carry candidate-patterns + Appendix A on the email-inference correction event
> 4. `planning/today.md` ← Day 10 task plan (this file; alignment-resolved per the prior session — operator decisions on all forks are ratified into the plan)
> 5. `planning/concierge-blueprint-v2.md` ← UI section as the v0.1 architectural reference
> 6. `planning/decisions/DECISIONS.md` — tail; especially `[2026-04-30 Day 9]` for prior context
>
> Today is Day 10 — UI day. Build all three sections to v0.1-quality per the task ladder. **No time-box, no scope-cap; build the right thing, not the shortest version.** Surface re-scope only on a fork or genuine architectural surprise — not on normal "task running long."
>
> Begin with Task 0. Two named surface checkpoints in the plan:
> - Task 1 Step 2: pick the data source for "most-used" aggregation (request rows / telemetry / recommend log) — surface before coding.
> - Task 2 Step 1: `name_q` substring filter on `/tools` — surface before adding.
>
> Effort: max throughout. UI-build work has both architectural decisions (composition pattern, partial-render boundary) and detail work (HTMX wiring, CSS polish); both warrant max.
>
> Discipline carry-forward (durable constraints from Days 2-9):
> - **Test-fails-first** for any new test landing on a fix
> - **Wiring tests assert client-observable contracts** — default rule, not aspiration; for the UI that means TestClient against rendered HTML with marker-string assertions, against the real Jinja+router stack, not mocked components
> - **Live shakedowns are fresh-session-only** for user-experience claims; Day 10 Task 5 is non-negotiable, with SSE-vs-polling-fallback validation specified at Step 4(c)
> - **Surface-then-execute** for architectural decisions
> - **Mid-stream re-surface** for forks
> - **In-place DECISIONS edits** OK for current-day entries; corrections to prior-day entries land in next snapshot
> - **Report between steps; proceed unless intervened**
> - **Time-box discipline does NOT apply to Day 10** — operator decision; build the right thing, not the shortest version
> - **Clean-baseline regression signal** with N≥5 flake-rate characterization for intermittent failures (Day 8 Appendix D refinement)
> - **Single-venv discipline** (candidate, Day 8): `.venv` is canonical when uv is the dependency manager
> - **Lewis/Lewie naming convention** (candidate, Day 9): Lewis (legal) public-facing; Lewie (operational) internal-only
> - **Read-after-edit for structural config files** (candidate, Day 9): edit-success ≠ semantic correctness; read pyproject back after Task 0 Step 1's `jinja2` addition before `uv sync`
> - **Public-contact-info-confirmation rule** (Day 9, codified durably via feedback memory): never infer email/phone/handle/real-name from git/env/auto-memory for public artifacts; always confirm with operator
>
> Do not begin code until I confirm the alignment (which has already happened — proceed once you've confirmed understanding of the plan).

---

*48h shakedown clock continues running cleanly through Day 9 — the day's changes touched docs (README, LICENSE, ABOUT.md, CLAUDE.md prune) and packaging metadata (pyproject.toml httpx classification + license/authors fields). None affect the recommend / SSE / lifecycle paths the shakedown exercises. Soak observations should land in the Day 10 SESSION snapshot.*

*Forward-carry items not in Day 10 scope (still outstanding from prior days, aggregated by source):*

- *Token-weight tracker (Day 10 alignment forward-carry) — measuring actual context-cost of each tool/MCP/skill at load time. Distinct from dropped tokens-saved feature.*
- *Whether Fork 1 / Fork 4 deserve formal DECISIONS entries post-hoc (Fix Day 3)*
- *Install-path auto-transition vs scanner-owned state changes (Fix Day 3 Question 2)*
- *Skills-specific "used" detection signal sources (Fix Day 3 Question 3 / Fix Day 4 Fork H)*
- *Loader-emit wiring scheduling (Fix Day 4 Open Question 2 — when first real backing-server registration arrives)*
- *Catalog-slug aliasing convention (Fix Day 5 — well-known-tool-name → slug helper)*
- *Venv-corruption-events Appendix as ops-protocol section (Day 7 Appendix C — candidate)*
- *Time-box discipline on ambiguous-scope investigations (Day 7 Appendix E — candidate)*
- *Single-venv discipline (Day 8 Appendix C — candidate)*
- *Clean-baseline-flake-rate refinement (Day 8 Appendix D — candidate)*
- *Lewis/Lewie naming convention (Day 9 — candidate)*
- *Read-after-edit discipline for structural config files (Day 9 — candidate)*
- *Vision-section "verbatim" preservation refinement (Day 9 — candidate)*
- *Public-contact-info-confirmation rule (Day 9 — codified via memory; awaits second data point for ops-protocol ratification)*
- *Flake-rate P2 investigation (Day 8 Appendix B; 1/5 = 20%) — pushed past Day 10 (no headroom given full-fidelity scope)*
