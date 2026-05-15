# Tool Manifest Fixture

> **Sanitization notice — Concierge is a public repo.**
> This fixture is a SYNTHETIC manifest built solely to exercise the
> H3+bullets parser shape used by the production manifest under
> `~/.agent-skills/shared/TOOL-MANIFEST.md`. All service names, paths,
> codes, prefixes, transports, and prose are fabricated. There are NO
> live API keys, NO real customer/account identifiers, NO real
> file paths from the operator's environment, NO real domain names.
> See `tests/test_ingest_tool_manifest.py::test_fixture_contains_no_real_credentials`
> for an automated check that no sensitive patterns (live key prefixes,
> real domains, real paths) have leaked in.

**Last Updated:** January 2026 (synthetic — not a real date stamp)
**Maintainer:** TEST_FIXTURE_OPERATOR
**Purpose:** Exercise the manifest parser; not a real capability registry.

---

## How to Use This Manifest

This section is informational prose. The parser passes it through
without consuming any tool entries.

---

## FLEET OVERVIEW

| Agent | Name | Port | Profile | Tools | Primary Role |
|-------|------|------|---------|-------|-------------|
| Primary | TestPrimary | 10000 | default | 12 | Synthetic primary |
| Worker A | TestWorkerA | 10001 | content | 8 | Synthetic worker |

This is a passthrough table — no tool entries here.

---

## ACTIVE CAPABILITIES — ALFRED (Primary, Port 10000)

### MCP Server: WidgetTool (6 tools)
- **Status:** ACTIVE | Transport: stdio (npx)
- **What it does:** Synthetic widget-management capability for tests.
- **Runs:** A test process, not a real binary.
- **Best for:** Exercising the full-fields parse path.
- **Limitation:** Not a real tool; do not invoke.
- **Prefix:** `widget_*`

### MCP Server: SecureWidget (4 tools)
- **Status:** ACTIVE | Transport: stdio (node) | Port: 9999
- **What it does:** Synthetic widget with restricted ownership.
- **Best for:** Testing the agent_owner path.
- **Only available to:** Alfred (workers use the unrestricted WidgetTool instead)
- **Prefix:** `secure_*`

### MCP Server: AuthedService (10 tools)
- **Status:** ACTIVE | Transport: stdio (uvx) | Auth: API key (Synthetic)
- **What it does:** Synthetic authenticated service for testing auth parsing.
- **Best for:** Exercising the compound-status Auth segment.
- **Only available to:** Alfred
- **Tools prefixed:** `authed_*`

### MCP Server: AnotherAuthed (3 tools)
- **Status:** ACTIVE | Transport: stdio (mcp-remote) | Auth: OAuth
- **What it does:** Another authenticated service variant.
- **Only available to:** Alfred
- **Prefix:** `another_*`

### MCP Server: Memory (8 tools)
- **Status:** ACTIVE | Transport: stdio (bash→python)
- **What it does:** Synthetic memory service shared by every test agent.
- **Tools:** memory_store, memory_search, memory_delete
- **Env var:** TEST_MEMORY_DIR

---

## ACTIVE CAPABILITIES — WORKER AGENTS

### TestWorkerA (Content Prep) — 8 tools
- WidgetTool (6) + Memory (8) + Filesystem (4)
- Memory at: `/tmp/test-memory-worker-a/`
- Skills at: `/tmp/test-skills-worker-a/`

### TestWorkerB (Engagement) — 5 tools
- WidgetTool (6) + UndocumentedTool (5)
- Memory at: `/tmp/test-memory-worker-b/`

---

## DISCORD VOICE PIPELINE

This is a passthrough section. No tool entries — infrastructure prose only.

---

## SHARED INFRASTRUCTURE

### Content Pipeline

This is a passthrough section (not under a tool-bearing H2).

---

## AD-HOC MCP ACCESS (test-porter)

**Status:** ACTIVE | Binary: `/tmp/test-porter` | Version: 0.0.0

test-porter is a synthetic ad-hoc MCP launcher for testing the H2-as-entry
parser path. The body is prose, not bullets.

**Usage:**
test-porter call --stdio "fake-server" tool-name '{"arg":"value"}'

**When to use:** Only inside tests.

**Available to:** All agents

---

## BUILDABLE (Custom Capabilities Needed)

### Synthetic Build A
- **Status:** NOT YET BUILT
- **What it would do:** Synthetic future capability for testing.
- **Current approach:** Manual.
- **Gap:** Nothing to build — this is a test fixture.

### Synthetic Build B
- **Status:** PARTIALLY BUILT
- **What it would do:** Another synthetic future capability.
- **Manual steps remain:** All of them; this is fixture data.

### Synthetic Build Unknown
- **Status:** SOMETHING-UNKNOWN
- **What it would do:** Tests the unknown-status fallback path (→ discovered + WARN).

---

## API KEYS & CREDENTIALS STATUS

| Service | Status | Location | Agent Access |
|---------|--------|----------|-------------|
| Synthetic-A | ACTIVE | (fictional) | Test agents only |

This is a passthrough table — no tool entries here.

---

## REQUESTING A NEW CAPABILITY

Passthrough instructional content.
