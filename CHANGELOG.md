# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

**Catalog** — SQLite-backed catalog of CLI tools, MCP servers, HTTP APIs, and skills as peer capability categories.
- Lifecycle state per row (discovered → pending → installed → loaded-on-boot → demoted → retired)
- Pack/tool relationships with stable per-pack ordering and "Unpacked" fallback for standalone tools
- `GET /tools` with combinable filters: `tool_type`, `category`, `lifecycle_state`, `pack_slug`, `install_method`, `is_active`, `is_in_manifest`, `name_q` (case-insensitive substring match against name OR slug)
- Markdown export per row

**Recommendation engine** — `POST /recommend` ranking via Anthropic Claude API.
- Structured response: ranked tool slugs, per-rec rationale, surfaced alternatives, confidence labels (`high` / `medium` / `low`)
- Semantic-memory hits surface prior decisions for similar tasks
- Latency breakdown and token-usage telemetry per call
- In-memory `RecommendCounters` for soak diagnostics

**Lifecycle state machine** — pending-request markdown files mediating operator approval.
- `POST /requests/{filename}/status` with `StatusChange` body for state transitions
- Approve / Deny / Defer transitions with comment routed to `conditions` (approve) or `notes` (deny + defer)
- Cron-driven folder reconciliation (`pending` / `resolved` / `archived`) follows status changes
- Invalid-transition guard (`409 Conflict`) prevents double-submit corruption

**Discovery engine** — capability scanner for catalog gaps.
- Scans package registries, awesome-lists, and GitHub for capabilities not yet catalogued
- Out-of-catalog alternatives surface alongside in-catalog recommendations
- `is_discovered` flag on Request rows distinguishes new-to-the-catalog tools from known ones

**Memory** — semantic-memory store for past tool decisions.
- ChromaDB backend with sentence-transformer embeddings (`all-MiniLM-L6-v2`)
- Memory hits surface in `/recommend` responses for similar prior tasks
- Defensive degradation: `/recommend` works without memory if the store is unavailable

**Telemetry** — observability for soak diagnostics.
- `tool_usage_events` table (`event_type` ∈ `recommended` / `installed` / `loaded` / `used`)
- `GET /stats/top-tools` aggregates the top-3 most-recommended tools
- Per-subsystem counter snapshots in the `/health` payload
- SSE streaming via `/ui/events` for `new_request` notifications

**MCP adapter** — stdio-spoken `concierge-shim` console script working with any MCP-compatible host (Claude Code primary; Claude Desktop and other MCP hosts via the standard protocol).
- Three native tool calls: `concierge_recommend`, `concierge_request_tool`, `concierge_list_active`
- Structured tool-call responses with rationale and alternatives
- MCP resources at `concierge://prompts/{name}.md` for narration-as-push fragments
- Identity refresh on loaded-on-boot boundary crossings

**Operator dashboard** — browser UI surfacing the operator-side observability surface.
- Stack: HTMX 2.0.10 + Pico.css 2.1.1 + Jinja2 3.1; vendored under `ui/static/vendor/` for offline-friendly reproducible builds
- Three panels: Tool Registry (cards-in-pack-groups, name/slug filter, two designed empty states), Pending Requests Inbox (per-card Approve/Deny/Defer with `hx-indicator` in-flight feedback), Health/Stats bar (status, catalog active/total, pending-aligned counter, scanner heartbeat, top-3 most-recommended)
- SSE-driven refresh via a vanilla `EventSource` shim that calls `htmx.ajax` on `new_request` events
- 10s HTMX polling fallback for non-event-driven counters
- Factory-only app composition (`ui.app:create_app` wraps `core.app.create_app`); `--factory` flag mandatory at launch

**Health endpoint** — `GET /health` operational pulse for 48h-shakedown diagnostics.
- Subsystem counters (recommend / lifecycle / memory) + catalog row counts + request counts
- Pending-request count mirrors the inbox query (`folder='pending' AND status='pending'`); `resolved` and `archived` remain folder-based as cron-reconciliation drift signal
- Never 500s on subsystem read errors; partial reads surface via `health_warnings`
- Scanner field reports last-run summary (`None` when no scan has run yet)

**Operations protocol** — codified working discipline at `planning/concierge-operations-protocol.md`.
- Session boundaries, handoff snapshot template, decision-log format
- Three ratified disciplines: decision-edit pattern (in-place same-day, next-snapshot for prior-day corrections); wiring-test default rule (operator-observable contracts exercise reality, not mocks); live-verify fresh-session-only for user-experience claims
- Surface-then-execute discipline at architectural decisions
- Effort-level guidance per phase
