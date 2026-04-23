# Blueprint-vs-implementation coverage audit
### Produced: 2026-04-23 (Day 4 morning, post scope-pivot handoff)

## Scope

This audit cross-references current Concierge implementation against two reference documents:

1. **`docs/concierge-blueprint-v2.md`** — architectural intent (primary source for ship-it-whole scope decisions)
2. **`_legacy/toolconcierge/TOOL-CONCIERGE-OVERVIEW.md`** — Claude-Code-generated summary of the OpenClaw first-draft reference implementation (secondary source, possible drift / smoothing / selective emphasis)

It consumes (and does not re-verify) the two prior Day-4 verification reports documented in `docs/handoff-2026-04-23-scope-pivot.md`:

- **Catalog multi-category gap** (three/four categories — MCP servers, CLI commands, HTTP/APIs, skills)
- **Three-part fidelity report** (proactive invocation, rich in-chat content, pending-file fidelity)

Citations below use `file:line` where the basis is code; otherwise cite blueprint-v2 / TOOL-CONCIERGE-OVERVIEW sections by name.

## Explicit exclusions

**Known gaps — see handoff for context, not re-audited here:**

- Push channel / proactive injection (Concierge-initiated agent-context messages) — verified ABSENT in three-part fidelity report Q1.
- Identity Notes (persistent first-glance tool-preference summary) — verified ABSENT in handoff §14 and `core/memory.py:42-45, 74-77`.
- Notification surface to the operator — verified ABSENT (file-system + chat are the only current surfaces; no push).

**OpenClaw-deployment-specific — not applicable to standalone v1 unless Lewie decides otherwise:**

- Multi-agent hierarchy (Alfred-primary + Scout/Dispatch/Radar/Bridge workers).
- Alfred-as-coordinator / worker escalation via `sessions_send`.
- **WhatsApp** as the specific real-time messaging channel (the dual-channel *concept* — real-time ping + durable filesystem record — stays in scope).
- Cron-based housekeeping *mechanism* (hourly cron moving files). The request-pipeline *semantics* (pending → resolved → archived, status-line-driven transitions) stays in scope and is fully implemented; whether the mover is cron, a lifespan task, or an endpoint is a v1 deployment decision.

## Source-conflict protocol

Where blueprint-v2 and TOOL-CONCIERGE-OVERVIEW disagree, the conflict is flagged in **§F** below rather than adjudicated. Lewie makes the call.

---

## §A — Blueprint-v2 §Architecture (component status)

Blueprint-v2 lists nine component headers under §Architecture (lines 41-144). Each gets a row below.

| # | Component | Blueprint promise (what's needed) | Current state | v1 load-bearing? | Sized fix — basis | Dependencies |
|---|---|---|---|---|---|---|
| A1 | **Catalog Service** | Generalize schema; SQLite-backed; UI + adapters query it; preserve markdown-export (blueprint:46-56) | **PARTIAL** — SQLite catalog + `/tools`, `/packs` endpoints live; 4 hand-seeded rows. Schema has free-text `install_method` + nullable `pack_id` but NO first-class `tool_type` enum distinguishing MCP / CLI / HTTP / skill. No catalog-ingest code path anywhere. No markdown-export either way. | **YES — load-bearing.** Public release cannot honestly call itself "platform-agnostic tool awareness" if the catalog can't model HTTP-API tools or skills as peers. | ~3-4h total: Layer-A schema `tool_type` enum (~1h, `core/db/models.py:33-52`), Layer-B catalog ingest parser (~2-3h, no file exists today; `core/ingest/tool_requests.py` is the *request* parser not the *catalog* parser). Markdown-export Phase-2 per blueprint:294. | None upstream. Unblocks A2 prompt awareness (HTTP/skill), B1 UI Registry honesty, and the category field on `RecommendationRecord`. |
| A2 | **Recommendation Engine** | Lift 5-step protocol (decompose → manifest → gap report → execute → log) to `POST /recommend` endpoint (blueprint:58-69) | **PARTIAL** — endpoint works end-to-end; Opus 4.7 with `effort=xhigh`, deterministic prompt composition, memory graceful-degradation, parse+validator pipeline (`core/recommend/service.py:101-262`). **BUT** the five-check sequence (memory → resolved → catalog → manifest → discovery) is collapsed into a single Opus call reading catalog + memory; "resolved requests" is NOT consulted as a separate pre-call step, and "manifest" is implicitly-the-same as "catalog." Discovery happens inside Opus reasoning, not as an explicit branch. | **PARTIAL — depends on scope.** Blueprint's protocol is explicit at the agent-behavior level; Concierge's engine collapses it by giving Opus the whole picture at once. Defensible architecture choice but it MAY lose the "previously denied → still denied" guardrail the overview flags (TOOL-CONCIERGE-OVERVIEW:110-112). Verify whether denial-recall is preserved via memory alone. | **If collapse is acceptable: 0h.** **If denial-recall must be structurally asserted: ~1h** add resolved-requests query to `recommend/service.py:99-122` (new step between memory and catalog). **Full five-check branching: ~2h.** | Memory (A3). Resolved-requests query would reuse `core/lifecycle_store/store.py`. |
| A3 | **Memory Service** | Make queryable from Concierge core; identity notes supported (blueprint:71-81) | **PARTIAL** — `MemoryClient.search()` / `store()` live (`core/memory.py:190, 280`). ChromaDB + sentence-transformers. `identity_get` / `identity_set` flagged as "not implemented (scope trim)" at `core/memory.py:40-45`. Identity collection name defined at `:74-77` but no consumer. | Identity-notes specifically: excluded per §Exclusions. Search+store surface: **YES load-bearing**, already works. | Search/store: 0h (done). Identity-notes wire-in: deferred per exclusions. | None. |
| A4 | **Loader/Proxy Layer** | Claude Code-specific adapter for live MCP load/unload; `load(tool_id)`, `unload(tool_id)`, `list_active()` implicit (blueprint:83-93 + handoff §5) | **PARTIAL** — backing-server framework exists at `adapters/claude_code/backing_server.py` (subprocess-backed MCP client) + `backing_server_registry.py`. `register(spec)` ≈ load (`:45`); `shutdown_all()` = bulk teardown (`:99`); `registered_prefixes()` returns prefix strings (`:119`). **Missing:** single-tool `unload(tool_id)`; rich `list_active()` API returning tool detail; hot-swap without session restart in a verified real-world test. | **YES — load-bearing for the pitch.** Blueprint §Demo scenario:255-265 and §Capability 5 ("agent proactively requests tools" → cron installs → session sees them) both presume hot-swap. Without unload and rich list_active, the operator can't exercise load/unload from the UI in a meaningful way. | ~1-1.5h: add `unload(tool_prefix)` to `BackingServerRegistry` (`backing_server_registry.py:29-120`); enrich `registered_prefixes()` to `list_active()` returning pack+tool detail; verify end-to-end with a fixture pack. | N13 backing-server-registry framework (present); dispatcher (present). |
| A5 | **Concierge Agent Interface — Pull channel** | Callable API so any agent interacts via HTTP or MCP, not just files (blueprint:95-104) | **FULL at the transport level** — 5 HTTP endpoints (`/health`, `/tools`, `/packs`, `/recommend`, `/requests`) + 3 MCP meta-tools (`concierge_recommend`, `concierge_request_tool`, `concierge_list_active`) all live. **PARTIAL at the behavioral level** — Three-part fidelity report Q1 found the pull-channel invocation is reactive, not proactive. MCP tool descriptions are terse (`adapters/claude_code/meta_tools/recommend.py:53-59`, `request_tool.py:39-46`) and the X3/X4/X6/X7/X8 behavioral instructions are wired to Opus-inside-recommend, not to Claude-Code-the-caller. | **YES — load-bearing.** The proactive-invocation gap is a real ship-it-whole concern: agents that don't spontaneously reach for Concierge make the whole system dependent on the user remembering to say "ask Concierge." | 0.5-1h (tool-description enrichment with X4 signal list); 1-2h (full MCP `resources/list` + `resources/read` route per `gap_preamble.py:52-58` deferred-plan). Both per three-part fidelity Q1 recommendation. | A1 (catalog needs the type data) + A2 (recommendations need to emit category/install_method/risk_cost for the rich in-chat surface). |
| A5b | **Concierge Agent Interface — Push channel** | Not explicit in blueprint but implied by overview's "proactive injection" pattern | **ABSENT — see handoff, known gap.** | (excluded) | (excluded) | (excluded) |
| A6 | **Lifecycle State Machine** | Wrap pending/resolved/archived folders with API; promotion/demotion criteria codified (blueprint:106-118) | **FULL for request-lifecycle**, **ABSENT for tool-lifecycle**. See §D below for the separate deep-dive on this. | (see §D) | (see §D) | (see §D) |
| A7 | **UI / Dashboard** | Three-section hackathon scope: Tool Registry, Pending Requests Inbox, Health/Stats Bar (blueprint:120-203) | **ABSENT** — `ui/` contains only `__init__.py`; `GET /ui` returns 404. The backing JSON endpoints all exist; the rendering layer does not. | **YES — load-bearing.** "Real operator UI" is a first-rank blueprint capability AND is what Day 4 was about to build before the scope-verification pause. | ~4-6h for minimum-viable three-tile dashboard per the proposal in SESSION opening today's context. That estimate assumes A1's catalog schema can already honestly render three peer categories. | A1 (Registry tile needs `tool_type`); A4 (Registry tile's "active" column needs `list_active()`); A6 (Inbox tile needs `/requests/pending` — already works); A8 wishlist tile (optional, read-only view). |
| A8 | **Failure Feedback Loop (wishlist)** | Read-only UI view of capability gap log; pattern recognition "3+ occurrences → candidate" documented in blueprint:126-133 | **ABSENT** — repo has zero wishlist-log code or storage. The `/requests` pipeline stores *structured tool-requests*; the wishlist in the overview is a *different* surface (a less-structured "I wanted X, didn't have it, worked around" log). `core/prompts/SKILL_FRAGMENT_SYNC_LOG.md:388-389` notes "lifecycle store absorbs the wishlist log" as an architectural decision — implying the intent was to collapse the two, but the code reflects no such absorption (wishlist doesn't appear in `core/lifecycle_store/` at all). | **PARTIAL load-bearing.** Blueprint marks it as Phase-2 ("Wishlist Patterns" in §Post-hackathon UI sections, blueprint:204-212). For ship-it-whole v1 it is deferrable **if** the intent to collapse into requests holds and is documented. | 0h if collapse holds (just document the decision); ~2-3h if standalone wishlist surface needs to exist (new table, endpoint, ingest path, UI tile). | Design decision: is wishlog a subset of requests or a separate type? |
| A9 | **Cross-Agent / Cross-Harness Learning** | Generalize "agent" to "any Concierge client"; shared memory/catalog across harnesses (blueprint:135-144, handoff §13) | **PARTIAL — architecturally enabled but not verified end-to-end.** ChromaDB store is single-DB; `core/memory.py:68-72` notes `COLLECTION_MEMORIES = "memories"` "must match moltbot-memory-mcp for cross-read compatibility on a shared store." No second harness has been wired in during this build (only Claude Code). | **PARTIAL load-bearing.** Ship-it-whole means at minimum "another harness *could* be wired in without schema surgery." The architectural claim holds; empirical verification is Phase-2 (OpenClaw adapter is explicitly §Phase 2 in blueprint:330). | 0h for v1 (architectural-claim-only, documented in `core/memory.py:68-77`). Verification happens when the second adapter is built. | Phase-2 work (OpenClaw or Claude Desktop adapter). |

---

## §B — Blueprint-v2 §"The UI in detail" — three hackathon sections

| # | Tile | Blueprint promise | Current state | v1 load-bearing? | Sized fix |
|---|---|---|---|---|---|
| B1 | **Tool Registry** | Hierarchical: packs → tools; rows show name, lifecycle state, transport type, owning agent(s), last used, success rate; filter by state + search (blueprint:181-187) | **ABSENT (rendering)** — backing `/tools` + `/packs` endpoints live. "Lifecycle state" column per blueprint needs **tool-level lifecycle** (§D — missing) OR the derived four-state `_tool_state` from `core/recommend/prompt.py:125-136`. "Transport type" needs A1's enum. "Last used" / "success rate" need usage telemetry (absent — see §C Memory and Learning). | **YES** — it's the headline section of the operator UI. | ~1-1.5h rendering if A1 + §D precede it; the tile is mostly plumbing. Without A1 and §D it can still render but will collapse three peer categories + obscure tool-level state. |
| B2 | **Pending Requests Inbox** | Card per request with structured markdown; Approve/Deny/Defer buttons posting to status endpoint; optional comment field (blueprint:189-195) | **ABSENT (rendering)** — `/requests/pending`, `/requests/{filename}/status` live; write path matches OpenClaw structure (three-part fidelity Q3 = FULL). | **YES** — second headline tile. | ~1-1.5h rendering. Lowest-risk tile — the data layer is already solid. |
| B3 | **Health / Stats Bar** | Four tiles: token-win counter, active MCP servers/total, cron last-run timestamp + heartbeat, top-3 tools (blueprint:197-202) | **PARTIAL** — `/health` provides config + counters + catalog counts + request counts + `fixture_drift` (`core/api/health.py:100-120`). **Missing:** token-win counter (N19 per build plan — not yet built); cron heartbeat (cron-mechanism is excluded, but a housekeeping-last-ran timestamp surface still needed); top-3 tools (needs usage telemetry). | **PARTIAL load-bearing.** The `/health` payload is genuinely operator-useful today. Token-win + top-3 tools + cron-heartbeat are demo-valuable but not prerequisites for "Concierge can be run and watched." | ~0.75h rendering for the existing fields; N19 token-win ~1h if included; top-3-tools needs usage-log ingestion (~1-2h). |

---

## §C — TOOL-CONCIERGE-OVERVIEW — subsystem coverage

Overview's eight subsystem headers (Recommendation Loop / Request Pipeline / Notification System / Autonomous Installation / Discovery Engine / Memory and Learning / Tool Lifecycle Management / Multi-Agent Architecture) mapped to current state. Where the overview goes deeper than blueprint-v2 on a topic already covered in §A above, I cite the §A row and only add the delta.

| # | Overview subsystem | Overview promise | Current state | v1 load-bearing? | Sized fix — basis | Dependencies |
|---|---|---|---|---|---|---|
| C1 | **Recommendation Loop** (overview:30-42) | Five checks in order: memory → resolved → catalog → manifest → discovery; complete task with current tools, never block | Covered in A2. Loop is **collapsed** into one Opus call; `core/recommend/service.py:101-122` orders memory → catalog → Opus (discovery folded into Opus reasoning via X6 `tool_discovery.py:71-178` prompt). "Never block" is captured on the adapter side in `CLAUDE_CODE_GAP_PREAMBLE` wording (but that preamble is deferred from Claude-Code-visible surface — see three-part Q1). | Same as A2 — acceptable collapse or ~1-2h to expand. | See A2. | See A2. |
| C2 | **Request Pipeline** (overview:44-60) | Three-folder pending/resolved/archived; six-value status; request schema (Request / Recommendation / Approval / Install / Outcome) | **FULL for pending→approved/denied/deferred/installed/failed transitions.** `core/lifecycle_store/transitions.py:30-38` encodes the file-side state machine. The five schema sections — Request / Recommendation / Approval / Install / First Use / Outcome — are in `core/ingest/tool_requests.py:176-230` as `_EXPORT_SECTIONS`; round-trip parse is verified on every write at `core/lifecycle_store/service.py:194-201`. Write path was confirmed byte-for-OpenClaw-structure in three-part fidelity Q3. | **FULL load-bearing** — this is the backbone of the operator workflow. | 0h (done). | — |
| C3 | **Notification System — dual channel** (overview:62-67) | WhatsApp ping (real-time) + filesystem (durable). Dual-surface is the design rule. | **PARTIAL** — filesystem is FULL (request files written atomically, round-trip-parse-verified). Real-time surface is ABSENT (no chat / SSE / webhook). WhatsApp specifically is excluded per §Exclusions but the *dual-channel concept* remains in scope. | **PARTIAL load-bearing.** Ship-it-whole needs *some* real-time surface — otherwise the operator has to poll the filesystem / UI to know a request was filed. | ~1-2h for a minimum-viable real-time surface — options are (a) SSE on the `/ui` dashboard (HTMX natively supports `hx-sse`), (b) a user-configurable webhook, (c) a desktop-notification shell-out. Choice is a design decision, not a patch. | UI (§B) is the natural home for SSE. |
| C4 | **Autonomous Installation** (overview:69-78) | npm-global / pip-user / single-binary / **npx-for-MCP** autonomous; sudo/money/new-accounts escalated; clear documented boundary | **PARTIAL** — three of four autonomous methods present: `install_npm_global` (`core/install/methods.py:41`), `install_pip_user` (`:52`), `install_single_binary` (`:62`). **Missing: npx-for-MCP** (the fourth autonomous method in overview:73-76). Boundary enforcement works *implicitly*: `core/install/service.py:35-68` `normalize_install_method` returns `None` for unrecognized/elevated methods, which the dispatcher treats as "operator must handle manually" (`:101-106`). **Not wired** into `core/lifecycle_store/service.py::update_status` — approve button doesn't trigger install (handoff §X13 wire-in). | **YES load-bearing.** An operator who approves a tool and then has to manually run `pip install --user csvkit` loses half the autonomy the pitch promises. | ~0.25h for X13 wire-in (approve → install via install_by_method); ~0.75h to add `install_npx_mcp(package)` method + normalizer signals. Total ~1h. | A6 request-lifecycle (done). |
| C5 | **Discovery Engine** (overview:82-102) | Package registries + awesome-lists + MCP server repos; five-signal filter (maintenance / adoption / license / install-weight / fit); `Discovered: true` provenance | **PARTIAL — present as prompt instruction, not as enforced filter.** `core/prompts/tool_discovery.py:118-136` contains the green/yellow/red signal table verbatim. It is composed into Opus's system prompt. **It is not enforced as Python filter logic** — Opus reads it and is expected to apply the criteria. `is_discovered` bool is preserved through parse/write/export (`core/db/models.py:66`, `core/ingest/tool_requests.py:148, 260`). No actual *calls* to npm/PyPI/GitHub registries happen from Concierge code — discovery is an Opus-reasoning surface. | **PARTIAL load-bearing.** For ship-it-whole, "Opus reads the signals and decides" is defensible if Opus is reliable, but the blueprint's "discovery engine" language (blueprint:67-69) hints at an actual web-search / registry-query surface. Worth asking Lewie. | 0h if Opus-reasoning surface is accepted. Full registry-query implementation is a major sub-project (~4-8h) and is almost certainly Phase 2. | — |
| C6 | **Memory and Learning** (overview:106-120) | Every decision `tool-selection` tagged; denials stay denied; duplicate-request prevention; Identity Notes | **PARTIAL — store works, retrieval works, identity notes absent.** `MemoryClient.search/store` + `tool-selection` tag constant at `core/lifecycle_policy.py:83-88`. Denial-recall happens IF memory surfaces the prior denial AND Opus honors it — no structural prevention. Duplicate-request prevention at file-level via `FileExistsError` (`core/lifecycle_store/writer.py:140-144`) but not at semantic level (same tool, different filename = two requests). Identity Notes: ABSENT per §Exclusions. | **PARTIAL load-bearing.** Memory tag + search = YES; denial-recall = implicit via Opus; duplicate prevention at file level only. | 0h for exclusions (identity). ~0.5h for semantic dup-check on tool-name match + open-request status. | — |
| C7 | **Tool Lifecycle Management** (overview:122-152) — promotion/demotion/weekly-review | Promotion 5+ uses/30d; demotion 90+ days unused; weekly-review scan for (a) promotion candidates, (b) demotion candidates, (c) stale pending >7d, (d) memory hygiene | **PARTIAL — constants extracted, endpoint/scanner absent.** `core/lifecycle_policy.py:139-160` defines `PROMOTION_MIN_USES=5, PROMOTION_WINDOW_DAYS=30, DEMOTION_INACTIVITY_DAYS=90, STALE_PENDING_DAYS=7` — thresholds match overview exactly. **No scanner implementation.** No endpoint exposes these. `GET /requests/pending?stale=true` filter at `core/api/requests.py:73-79` is the only consumer of `STALE_PENDING_DAYS` — and that's only for the stale-pending-flag. Usage telemetry (needed for promotion/demotion) is not recorded anywhere — there is no "tool was used N times" count on the Tool model. | **PARTIAL load-bearing.** Promotion/demotion UI is flagged as Phase-2 in blueprint:204-212 ("Settings — adjust thresholds"). For ship-it-whole v1, the *constants exist in the codebase* is honest coverage; the *scanner/endpoint* is deferrable. **BUT** usage telemetry is a foundational prerequisite that also blocks B1's "last used / success rate" column and B3's "top 3 tools" tile — those are UI items blueprint puts in hackathon scope. | ~2-3h total if ship-it-whole wants full lifecycle scanner (usage-log table + scanner + endpoint + weekly-review output). ~0.5h if the ship is "constants are defined; scanner is Phase-2; UI columns show blanks for now." | Usage telemetry table (new) — foundational. §D tool-lifecycle state machine (absent). |
| C8 | **Multi-Agent Architecture** (overview:156-188) | Alfred-primary + worker escalation + dual-channel | **N/A** per §Exclusions (OpenClaw-deployment-specific). | N/A | — | — |

---

## §D — Tool-level vs request-level lifecycle separation (explicit deep-dive)

**Question:** Does `core/lifecycle_store/` silently handle both tool-level and request-level state, or cleanly separate them? If conflated, design-level flag.

### The three lifecycle state machines blueprint-v2 / overview imply

1. **Request-lifecycle.** States: `pending → approved | denied | deferred | installed | failed`. About an individual tool-request file moving through human review + install. Source: blueprint:109-110, overview:44-60.
2. **Memory-entry lifecycle.** States: `pending → approved → installed → removed`, plus `denied` and `failed`. About a single tool-selection memory entry's evolution over a tool's life. Source: X7-A tool-lifecycle skill / `core/lifecycle_policy.py:99-119`.
3. **Tool-lifecycle.** States: `discovered → pending → used → loaded-on-boot → retired` (five states). About a tool's career on this machine — from first recommendation to eventual retirement. Source: handoff §4 + implied by blueprint:186 ("lifecycle state") + overview:124-152 (promotion/demotion language).

### Current code: how cleanly are they separated?

**#1 and #2 are cleanly separated and explicitly documented as such.**

- `core/lifecycle_store/transitions.py:1-19` docstring names the distinction by name: "File-side (X10 README): pending, approved, denied, installed, failed, deferred. Memory-side (X7-B policy): pending, approved, installed, denied, failed, removed. `deferred` is a human 'later' disposition; `removed` does not exist at this layer." The module explicitly warns callers not to import the memory-side table and use it as the authority.
- `core/lifecycle_store/transitions.py:30-38` implements #1.
- `core/lifecycle_policy.py:99-119` implements #2 (as a constant, consumed by future lifecycle scanner + memory-tagging writers).
- Zero silent overlap. The separation is a load-bearing design decision from Day 2 (DECISIONS `[2026-04-22 08:34]`'s rename from `lifecycle.py` to `lifecycle_policy.py`).

**#3 (tool-lifecycle) is ABSENT as a state machine.** What exists in its place:

- **Derived four-state label** at `core/recommend/prompt.py:125-136`: `_tool_state(is_in_manifest, is_active)` maps `(bool, bool)` to one of `active / dormant / pending / retired`. This is what Opus sees in the rendered catalog. It is *computed from the two Tool bool fields, not stored, not transitioned.*
- **No usage count on the Tool model** (`core/db/models.py:33-52`). The "used" state from blueprint's five-state machine has no backing field.
- **No "loaded-on-boot" distinction** separate from `is_active`. The backing-server registry tracks which packs are loaded (`adapters/claude_code/backing_server_registry.py`) but that state is **in-process-memory only** and is not persisted to the Tool table.
- **No retirement workflow** — setting `is_in_manifest=False, is_active=False` would produce the `retired` label but there's no endpoint or UI affordance to do so intentionally.

### Design-level flag

**This is design-level, not patch-level.** Adding the tool-lifecycle state machine is not "add a Python enum"; it is:

1. **Schema change:** new column `Tool.lifecycle_state` (or equivalent) on `core/db/models.py:33`. Alembic migration. Backfill for the 4 existing rows.
2. **Usage-log table:** a `ToolUsageEvent` (or similar) table to support the "used" state and feed promotion/demotion. No such table exists.
3. **Transition validation:** a `tool_transitions.py` table of legal transitions mirroring `lifecycle_store/transitions.py`. Which events trigger which transitions (`concierge_recommend` returning this tool = "used"? A `concierge_request_tool` filed for it = "pending"? Loader-layer `load()` call = "loaded-on-boot"?) is a decision you have to make.
4. **Derived-label migration:** `_tool_state` at `core/recommend/prompt.py:125-136` becomes a transitional artifact — either retired in favor of the stored state, or kept as a mapping for backward compatibility.
5. **UI implication:** blueprint:186 says the Registry row shows "lifecycle state." Without #3 existing, the UI either (a) renders the `_tool_state` derived label honestly (four states, not five), or (b) fabricates a state it doesn't have.

**Verdict:** the request-level and memory-entry-level state machines are cleanly separated, well documented, and implementation-faithful. The tool-level state machine is a **missing architectural component**, not a conflation. This is load-bearing for ship-it-whole **if** the UI is expected to surface lifecycle state per blueprint:186 and **if** promotion/demotion per overview:122-152 is expected to work on real usage data.

**Sized fix:** ~4-5h total (schema 1h + usage-log table 1h + transition table 1h + backfill 0.5h + derived-label migration 0.5-1h). Does not include the scanner/cron that would drive transitions automatically; that's another ~2-3h on top per §C7.

---

## §E — Dependency rollup

Reading the rows above as a graph:

- **A1 (catalog schema `tool_type`)** unblocks: A5 (richer meta-tool surface), B1 (honest Registry rendering), and the category/install_method/risk_cost fields on `RecommendationRecord` from three-part fidelity Q2.
- **§D (tool-lifecycle)** unblocks: B1 (lifecycle-state column), B3 (top-3-tools tile), C7 (promotion/demotion scanner).
- **C4 (X13 wire-in)** unblocks: B2 (approve-triggers-install demo-moment), which is the pitch beat in blueprint:258-261.
- **A4 (loader `unload` + rich `list_active`)** unblocks: B1 (active-vs-inactive Registry column with meaningful data).
- **A7 (UI shell + three tiles)** consumes all of the above.

**Foundational items (no upstream):** A1, §D, C4, A4.
**Consumer items (depend on ≥1 foundational):** A2 (if resolved-check added), A5, B1, B2, B3, C3, C7.

**Minimum load-bearing cluster for ship-it-whole v1** if the call is "close gaps before UI":

| Cluster | Items | Sized | What it buys |
|---|---|---|---|
| "Honest catalog" | A1 schema + catalog ingest | 3-4h | Three (or four with skills) peer categories land. HTTP/API tools finally expressible. |
| "Honest tool-lifecycle" | §D | 4-5h | The blueprint:186 "lifecycle state" column is truthful when the UI lands. |
| "Approve actually works" | C4 X13 wire-in + npx-MCP | ~1h | Inbox approval triggers install; matches blueprint:258-261 demo beat. |
| "Loader honest" | A4 `unload` + rich `list_active` | ~1-1.5h | Operator can exercise load/unload from the UI. |
| "Rich in-chat content" | schema + prompt + validator for category/install_method/risk_cost | ~1-1.5h | Three-part fidelity Q2 closed. |
| "Proactive invocation" | tool-description enrichment (minimum) | ~0.5-1h | Three-part fidelity Q1 partially closed; full fix (resources protocol) deferrable. |
| "Dual-channel real-time" | SSE on `/ui` dashboard | ~1-2h | Notification-dual-channel-concept satisfied without WhatsApp coupling. |

**Rough ship-it-whole foundation total before UI work:** ~12-16h of non-UI fix work. UI itself (A7) is another ~4-6h on top, for a combined ~16-22h before Day-5 shakedown.

**Deferrable to Phase 2 under ship-it-whole scope:**

- Promotion/demotion scanner + weekly-review (C7 minus constants) — ~2-3h, Phase-2.
- Discovery-engine actual registry queries (C5 beyond prompt-only) — ~4-8h, Phase-2.
- Cross-harness learning empirical verification (A9) — gated on second-adapter build.
- Wishlist surface (A8) — design-decision-dependent; may collapse into requests.

---

## §F — Source conflicts between blueprint-v2 and TOOL-CONCIERGE-OVERVIEW

Instances where the two documents disagree. Flagged, not adjudicated.

| # | Topic | Blueprint-v2 says | Overview says | Delta |
|---|---|---|---|---|
| F1 | Number of catalog categories | "transport types" (plural, unspecified count); blueprint:49,185 | Three explicit top-level sections in legacy `TOOL-CATALOG.md`: MCP Servers / CLI Tools / Paid Services (implied HTTP/API); four-category set enters via handoff citing "Skills" as a fourth peer. | Blueprint is underspecified on count; overview implies three; handoff says four. Catalog gap report from yesterday surfaced three; skill-as-category was listed as "likely present" in handoff §1. **Needs Lewie ruling.** |
| F2 | Wishlist vs requests | Blueprint:127-133 names wishlist as a distinct surface with Phase-2 UI ("Wishlist Patterns"). Hackathon scope is "read-only view." | Overview does not list a dedicated wishlist section; gap-log appears only in X3 tool_awareness prompt instruction (`core/prompts/tool_awareness.py:97, 190`). | **Implicit design drift.** `core/prompts/SKILL_FRAGMENT_SYNC_LOG.md:388-389` notes "lifecycle store absorbs the wishlist log" — but that collapse is not reflected in code or blueprint. **Needs Lewie ruling:** are wishlog and requests two things or one? |
| F3 | Lightweight-first preference | Blueprint §demo scenario:262-265 calls lightweight-first preference a measurable outcome ("token counter… saved roughly 40K tokens"). N19 token-win instrumentation in build plan. | Overview does not mention token counting; lightweight-first is present only as a prompt-level preference in the behavior rules. | Blueprint adds a *measurement*; overview has only the *preference*. The measurement (N19) is not built. **Ship-it-whole question:** is the measurement demo-specific or operator-useful? |
| F4 | MCP load/unload ownership | Blueprint:86-91 explicitly names the Claude-Code MCP load/unload mechanism as the major *new work*. | Overview scopes load/unload broadly as "the system's job"; doesn't differentiate harnesses. | Minor — blueprint is more precise. No contradiction, just specificity. |
| F5 | Installation method inventory | Blueprint:85 lists "npm-global, pip-user, single-file binaries, MCP via npx" (four). | Overview:71-77 same four list. | *Consistent with each other*; Concierge code has *three* (`install_npm_global`, `install_pip_user`, `install_single_binary` — MCP-via-npx missing). **Concierge vs both sources = gap.** |

---

## §G — Audit summary (read this if nothing else)

**Verified FULL** — no additional work needed for ship-it-whole v1:

- Request Pipeline (C2) — three-folder state machine, file round-trip, DB reconcile at startup.
- Memory Service search/store surface (A3 minus identity).
- Transport-level Agent Interface (A5, HTTP + MCP meta-tools all reachable).
- Lifecycle separation between request-level and memory-entry-level (§D — the *existing* two machines are cleanly separated and documented; the *third* missing machine is a separate concern).
- X13 install-method dispatcher + three autonomous install handlers (C4 minus npx-MCP and minus wire-in).

**Verified PARTIAL — load-bearing for v1:**

- Catalog multi-category (A1) — HTTP/API and skills cannot currently be expressed as peers; schema change required.
- Tool-level lifecycle state machine (§D) — architectural gap, not a patch. Blueprint:186 UI column needs this.
- Loader `unload` + rich `list_active` (A4) — current framework has bulk shutdown only.
- X13 wire-in to approve flow (C4) — the "approve → install" demo beat fails without it.
- Rich in-chat recommendation content (A5 + three-part Q2) — three fields missing from schema.
- Proactive invocation (A5 + three-part Q1) — prompt surface only reaches Opus-inside-recommend.
- Dual-channel real-time surface (C3) — filesystem works, real-time is ABSENT.

**Verified PARTIAL — deferrable to Phase 2:**

- Recommendation five-check loop explicit branching (A2) — collapsed into Opus reasoning; acceptable if Lewie approves.
- Promotion/demotion scanner (C7) — constants exist, scanner absent; blueprint marks as Phase-2.
- Discovery engine real registry queries (C5) — Opus-reasoning surface works today; full registry-query is Phase-2.
- Wishlist surface (A8) — design-decision-pending.
- Cross-harness learning empirical verification (A9) — gated on second adapter.

**Verified ABSENT — excluded from this pass:** push channel, identity notes, notification surface (real-time); multi-agent, WhatsApp, cron mechanism. All excluded per handoff scope.

**Source-conflict flags (§F):** five conflicts surfaced; two need Lewie adjudication (F1 category-count, F2 wishlist-vs-requests); one exposes a Concierge gap vs both sources (F5 npx-MCP missing).
