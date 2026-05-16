"""Parse `~/.agent-skills/shared/TOOL-MANIFEST.md` and upsert tool rows.

Stage 1A item 7. Sibling to `core/ingest/catalog.py` (which parses the
older table-based TOOL-CATALOG.md) and `core/ingest/skills.py` (which
walks SKILL.md frontmatter). This module handles the H3+bullets format
of the live manifest.

Section dispatch
----------------

The manifest's 11 H2 sections split into four parser kinds + seven
passthroughs:

  parsed:
    `## ACTIVE CAPABILITIES — ALFRED`     → H3 blocks parsed as mcp tools
    `## ACTIVE CAPABILITIES — WORKER AGENTS` → H3 blocks parsed for
                                              agent cross-references only
                                              (do NOT emit tool rows)
    `## AD-HOC MCP ACCESS (mcporter)`     → H2 body parsed as a single
                                              cli tool (the special
                                              H2-as-entry case)
    `## BUILDABLE (Custom Capabilities Needed)` → H3 blocks parsed as
                                              tools with
                                              lifecycle_state=pending-decision

  passthrough (not consumed):
    `## Complete Capability Registry...`, `## How to Use This Manifest`,
    `## FLEET OVERVIEW`, `## DISCORD VOICE PIPELINE`,
    `## SHARED INFRASTRUCTURE`, `## API KEYS & CREDENTIALS STATUS`,
    `## REQUESTING A NEW CAPABILITY`

Bullet model
------------

Tool entries carry their data in `- **Key:** value` bullets (list form,
used by ALFRED + BUILDABLE) or `**Key:** value` paragraph-form (used
only by AD-HOC MCP ACCESS). Both forms are recognized.

The `**Status:**` bullet is COMPOUND — its value may carry
`|`-delimited segments that are themselves `Key: value` pairs. The
parser splits the Status value on ` | `, treats the first segment as
the lifecycle status word(s), and routes the remaining segments
through the same key-dispatch as standalone bullets.

Ten bullet keys are CONSUMED (map to DB columns):
  Status, Transport, Auth → lifecycle_state / transport / auth
  What it does / What it would do → description
  Best for → best_for
  Limitation → limitation
  Only available to → agent_owner
  Prefix / Tools prefixed → prefix

Eighteen+ keys are INFORMATIONAL and dropped: Runs, Extension, Secret,
Tools, Env var, Model, Storage, Server location, Critical rule, TODO,
Important, Output directory, Domain, Key data, Current approach,
Current state, Manual steps remain, Dependencies, Gap, Build approach,
Available to, Each agent has its own memory directory, Alfred's
Discord voice. Unknown keys are dropped with a WARN log so manifest
drift surfaces.

Normalization at parse time
---------------------------

The parser stores values in canonical form so DB queries are
predictable:
  - agent_owner / auth: stripped + lowercased
  - prefix: surrounding backticks stripped, stripped of whitespace
  - description / best_for / limitation: leading/trailing whitespace
    stripped, internal runs of whitespace collapsed to single space
  - transport, name: whitespace stripped only

The exporter (`dump_manifest`) re-presents canonical values in a
human-pleasing form (capitalized agent_owner, backticked prefix) so
the emitted markdown reads naturally. The parser+exporter pair is a
faithful inverse on the parsed-field set — parse(emit(parse(x))) is
equivalent to parse(x) under `equivalent()` (see below).

Idempotency
-----------

Upsert by slug = slugify(name). On NEW row, every parsed field lands
verbatim. On EXISTING row, descriptive fields (description, best_for,
limitation, prefix, transport, auth, agent_owner) are refreshed from
source; operator-managed fields are preserved:
  - `lifecycle_state` if it has moved away from `discovered`
  - `succeeded_by` if non-NULL (the parser never sets this; the
    Stage-0 reconciliation slice is the sole writer)
  - `is_active`, `is_in_manifest` once initialized

Matches catalog.py / skills.py upsert discipline.

Round-trip equivalence
----------------------

`equivalent(left, right)` applies the parse-time normalizations to
both ManifestRows and compares the Category-II fields field-by-field.
The test surface uses this as the definition of round-trip correctness:
parse → dump → re-parse must yield rows that satisfy `equivalent()`
against the originals.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

from sqlalchemy.orm import Session

from core.db.models import Tool
from core.ingest.tool_requests import slugify


log = logging.getLogger("concierge.ingest.manifest")


# ---- Section taxonomy ----------------------------------------------------


_SECTION_ALFRED = "alfred"
_SECTION_WORKER = "worker"
_SECTION_MCPORTER = "mcporter"
_SECTION_BUILDABLE = "buildable"
_SECTION_PASSTHROUGH = "passthrough"


_H2_TO_SECTION_KIND: dict[str, str] = {
    # Tool-bearing sections — exact H2 titles (modulo whitespace).
    "ACTIVE CAPABILITIES — ALFRED": _SECTION_ALFRED,
    "ACTIVE CAPABILITIES — WORKER AGENTS": _SECTION_WORKER,
    "AD-HOC MCP ACCESS (MCPORTER)": _SECTION_MCPORTER,
    "BUILDABLE (CUSTOM CAPABILITIES NEEDED)": _SECTION_BUILDABLE,
    # Synthetic sections used by the exporter (parsed back when
    # round-tripping). The exporter emits buildables/mcporter under
    # these uppercase canonical headers; the parser recognizes them.
    "AD-HOC MCP ACCESS": _SECTION_MCPORTER,
    "BUILDABLE": _SECTION_BUILDABLE,
}


def _classify_h2(title: str) -> str:
    """Return the section kind for an H2 title. Matches by the leading
    portion of the title (case-insensitive), tolerating " (Primary, Port ...)"
    or similar trailing parentheticals on the Alfred section."""
    norm = title.strip().upper()
    # Strip a trailing parenthetical group (e.g., " (PRIMARY, PORT 18789)").
    norm_base = re.sub(r"\s*\([^)]*\)\s*$", "", norm).strip()
    if norm in _H2_TO_SECTION_KIND:
        return _H2_TO_SECTION_KIND[norm]
    if norm_base in _H2_TO_SECTION_KIND:
        return _H2_TO_SECTION_KIND[norm_base]
    # Special case: "AD-HOC MCP ACCESS (mcporter)" keeps its parenthetical
    # (it names the tool inside the section). Hit it via norm_base check
    # against the version with the parenthetical retained.
    if "AD-HOC MCP ACCESS" in norm:
        return _SECTION_MCPORTER
    return _SECTION_PASSTHROUGH


# ---- Status word → lifecycle_state mapping -------------------------------


_STATUS_TO_LIFECYCLE: dict[str, str] = {
    "ACTIVE": "loaded-on-boot",
    "NOT YET BUILT": "pending-decision",
    "PARTIALLY BUILT": "pending-decision",
}


def _status_to_lifecycle(status_word: str) -> str:
    """Map a manifest Status string to a Tool.lifecycle_state value. Unknown
    statuses fall back to `discovered` and log WARN so manifest drift
    surfaces without halting ingest."""
    upper = status_word.strip().upper()
    if upper in _STATUS_TO_LIFECYCLE:
        return _STATUS_TO_LIFECYCLE[upper]
    log.warning(
        "manifest.unknown_status status=%r falling back to discovered",
        status_word,
    )
    return "discovered"


# ---- ManifestRow ---------------------------------------------------------


@dataclass
class ManifestRow:
    """One tool entry parsed from the manifest. Field set mirrors the
    Tool model's parser-touched columns; the remaining Tool columns
    (id, created_at, updated_at, etc.) are DB-managed."""

    name: str
    slug: str
    tool_type: str | None
    description: str | None
    lifecycle_state: str
    is_active: bool
    is_in_manifest: bool
    agent_owner: str | None
    best_for: str | None
    limitation: str | None
    prefix: str | None
    transport: str | None
    auth: str | None


@dataclass
class ManifestIngestStats:
    """Telemetry from one ingest run. `sections_parsed` is the count of
    H2 sections the dispatcher routed to a parser; `sections_skipped`
    counts the passthrough H2s.

    `cross_references_resolved` counts worker-section tool references
    whose H3 entries exist in Alfred's section; `cross_references_skipped`
    counts worker-only references with no Alfred H3 (logged WARN per
    Decision 4a — no auto-create)."""

    tools_created: int = 0
    tools_updated: int = 0
    cross_references_resolved: int = 0
    cross_references_skipped: int = 0
    sections_parsed: int = 0
    sections_skipped: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)


# ---- Regexes (compiled once) ---------------------------------------------


_H2_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.MULTILINE)
_H3_RE = re.compile(r"^###\s+(?P<title>.+?)\s*$", re.MULTILINE)

# H3 title patterns per section kind.
_H3_ALFRED_RE = re.compile(
    r"^MCP Server:\s+(?P<name>.+?)(?:\s+\((?P<count>\d+)\s+tools?\))?$"
)
_H3_WORKER_RE = re.compile(
    r"^(?P<agent>\w+)\s+\([^)]+\)\s+—\s+(?P<count>\d+)\s+tools$"
)
_H3_BUILDABLE_RE = re.compile(r"^(?P<name>.+?)$")

# Bullets — list form (`- **Key:** value`) and paragraph form
# (`**Key:** value`). The mcporter H2-as-entry uses paragraph form.
_BULLET_RE = re.compile(
    r"^(?:-\s+)?\*\*(?P<key>[^:]+?):\*\*\s*(?P<value>.*)$"
)

# Worker-section inline tool list: "Firefox DevTools (24) + Memory (8) + Filesystem (14)"
_WORKER_TOOL_LIST_RE = re.compile(
    r"^-\s+(?P<tools>[A-Za-z][A-Za-z0-9 \-]*(?:\s*\(\d+\))?(?:\s+\+\s+[A-Za-z][A-Za-z0-9 \-]*(?:\s*\(\d+\))?)*)\s*$"
)

# Per-tool reference inside a worker tool list: "Firefox DevTools (24)" or "Memory (8)"
_WORKER_TOOL_ITEM_RE = re.compile(
    r"^(?P<name>[A-Za-z][A-Za-z0-9 \-]*?)(?:\s*\(\d+\))?$"
)


# ---- Bullet key dispatch -------------------------------------------------


# Keys that route to a ManifestRow field, normalized to lowercase
# without trailing colon. The Status key is special (compound).
_BULLET_KEY_DESTINATIONS: dict[str, str] = {
    "what it does": "description",
    "what it would do": "description",
    "best for": "best_for",
    "limitation": "limitation",
    "only available to": "agent_owner",
    "prefix": "prefix",
    "tools prefixed": "prefix",  # MailerLite-style alias
    "transport": "transport",  # appears only inside compound Status
    "auth": "auth",  # appears only inside compound Status
}


# Keys explicitly recognized as informational (drop silently, no WARN).
_BULLET_KEY_INFORMATIONAL: frozenset[str] = frozenset({
    "runs",
    "extension",
    "secret",
    "tools",
    "env var",
    "model",
    "storage",
    "server location",
    "critical rule",
    "todo",
    "important",
    "output directory",
    "domain",
    "key data",
    "current approach",
    "current state",
    "manual steps remain",
    "dependencies",
    "gap",
    "build approach",
    "available to",
    "each agent has its own memory directory",
    "alfred's discord voice",
    # Inside compound Status: informational segments.
    "port",
    "key",
    "binary",
    "version",
})


# ---- Normalization helpers -----------------------------------------------


def _norm_prose(s: str | None) -> str | None:
    """Strip leading/trailing whitespace; collapse internal whitespace
    runs to single space. For prose fields (description, best_for,
    limitation)."""
    if s is None:
        return None
    collapsed = re.sub(r"\s+", " ", s).strip()
    return collapsed or None


def _norm_strip(s: str | None) -> str | None:
    """Whitespace strip only, preserve internal spacing. Used for fields
    where internal characters matter (transport's "stdio (npx)" etc.)."""
    if s is None:
        return None
    return s.strip() or None


def _norm_lower_strip(s: str | None) -> str | None:
    """Strip + lowercase. For canonical agent_owner / auth storage."""
    if s is None:
        return None
    out = s.strip().lower()
    return out or None


def _norm_prefix(s: str | None) -> str | None:
    """Strip whitespace + surrounding backticks. Manifest writes
    `` `firefox_*` ``; canonical storage is `firefox_*`."""
    if s is None:
        return None
    out = s.strip()
    # Strip ONE layer of backticks if present (don't recurse).
    if out.startswith("`") and out.endswith("`") and len(out) >= 2:
        out = out[1:-1]
    return out.strip() or None


def _norm_agent_owner_first_word(s: str | None) -> str | None:
    """Extract the first word from an `Only available to: <agent>` value.
    Source might be "Alfred (worker agents use ...)" — the first
    whitespace-delimited token is the agent codename. Lowercased."""
    if s is None:
        return None
    out = s.strip()
    if not out:
        return None
    # First token is the agent name; anything after is a parenthetical
    # comment ("Alfred (worker agents use ...)").
    first = out.split()[0]
    # If the first token is itself in parentheses (rare), strip them.
    first = first.strip("(),")
    return first.lower() or None


# ---- Compound Status parser ----------------------------------------------


def parse_compound_status_line(value: str) -> dict[str, str]:
    """Parse the value of a `**Status:**` bullet into its segments.

    The Status value is split on ` | `. The first segment is the status
    word(s) (e.g., `ACTIVE` or `NOT YET BUILT`). Subsequent segments are
    `Key: value` pseudo-bullets routed through the standard bullet
    dispatch (Transport, Auth, etc. mapped to fields; Port/Key/Binary/
    Version dropped as informational; unknown keys WARN-dropped).

    Returns a dict keyed by destination field name (e.g.,
    `lifecycle_status_word`, `transport`, `auth`) — the caller maps
    `lifecycle_status_word` to `lifecycle_state` via `_status_to_lifecycle`.
    """
    out: dict[str, str] = {}
    if not value:
        return out
    parts = [p.strip() for p in value.split("|")]
    if not parts:
        return out
    # First segment: the status word(s). Strip trailing whitespace.
    out["lifecycle_status_word"] = parts[0].strip()
    for segment in parts[1:]:
        if not segment:
            continue
        if ":" not in segment:
            log.warning(
                "manifest.malformed_status_segment segment=%r", segment
            )
            continue
        sub_key, _, sub_value = segment.partition(":")
        sub_key_norm = sub_key.strip().lower()
        sub_value_norm = sub_value.strip()
        if sub_key_norm in _BULLET_KEY_INFORMATIONAL:
            continue
        dest = _BULLET_KEY_DESTINATIONS.get(sub_key_norm)
        if dest is None:
            log.warning(
                "manifest.unknown_status_segment_key key=%r segment=%r",
                sub_key, segment,
            )
            continue
        out[dest] = sub_value_norm
    return out


# ---- H3 block parser -----------------------------------------------------


def _parse_h3_block(
    title: str, body_lines: list[str], section_kind: str
) -> ManifestRow | None:
    """Parse one H3 + its bullets into a ManifestRow. Returns None if
    the title doesn't match the expected pattern for this section kind."""

    name: str | None = None
    tool_type: str | None = None
    if section_kind == _SECTION_ALFRED:
        m = _H3_ALFRED_RE.match(title)
        if m is None:
            log.warning("manifest.malformed_h3_alfred title=%r", title)
            return None
        name = m.group("name").strip()
        tool_type = "mcp"
    elif section_kind == _SECTION_BUILDABLE:
        m = _H3_BUILDABLE_RE.match(title)
        if m is None:
            return None
        name = m.group("name").strip()
        tool_type = None  # buildables genuinely unclassified per Decision 4
    elif section_kind == _SECTION_MCPORTER:
        # The parser may be invoked with an H3 form (synthetic, from
        # the exporter) where the title is just the tool name. The
        # actual source manifest has mcporter as an H2-with-prose-bullets
        # entry handled separately by _parse_mcporter_h2; here we only
        # see the round-trip-emitted H3 form.
        name = title.strip()
        tool_type = "cli"
    else:
        return None

    if not name:
        return None

    parsed: dict[str, str | None] = {
        "description": None,
        "best_for": None,
        "limitation": None,
        "prefix": None,
        "transport": None,
        "auth": None,
        "agent_owner": None,
    }
    status_word: str | None = None

    for line in body_lines:
        bullet_match = _BULLET_RE.match(line.strip())
        if bullet_match is None:
            continue
        key = bullet_match.group("key").strip().lower()
        value = bullet_match.group("value").strip()

        if key == "status":
            status = parse_compound_status_line(value)
            status_word = status.pop("lifecycle_status_word", None)
            # Sub-segments (Transport / Auth / etc.) merge into parsed.
            for dest, sub_val in status.items():
                parsed[dest] = sub_val
            continue
        if key in _BULLET_KEY_INFORMATIONAL:
            continue
        dest = _BULLET_KEY_DESTINATIONS.get(key)
        if dest is None:
            log.warning(
                "manifest.unknown_bullet_key key=%r in name=%r", key, name,
            )
            continue
        parsed[dest] = value

    # Status → lifecycle_state.
    if status_word is None:
        # No Status bullet — default to discovered with WARN.
        log.warning("manifest.missing_status name=%r", name)
        lifecycle_state = "discovered"
    else:
        lifecycle_state = _status_to_lifecycle(status_word)
    is_active = lifecycle_state == "loaded-on-boot"

    return ManifestRow(
        name=_norm_strip(name) or "",
        slug=slugify(name),
        tool_type=tool_type,
        description=_norm_prose(parsed["description"]),
        lifecycle_state=lifecycle_state,
        is_active=is_active,
        is_in_manifest=True,
        agent_owner=_norm_agent_owner_first_word(parsed["agent_owner"]),
        best_for=_norm_prose(parsed["best_for"]),
        limitation=_norm_prose(parsed["limitation"]),
        prefix=_norm_prefix(parsed["prefix"]),
        transport=_norm_strip(parsed["transport"]),
        auth=_norm_lower_strip(parsed["auth"]),
    )


def _parse_mcporter_h2(
    h2_title: str, body_lines: list[str]
) -> ManifestRow | None:
    """Parse the special H2-as-entry case for mcporter.

    Source format under `## AD-HOC MCP ACCESS (mcporter)`:
      **Status:** ACTIVE | Binary: ... | Version: ...
      <prose>
      **Available to:** All agents (binary is on the system PATH)
      ...

    The parser only consumes recognized bullets. Description stays NULL
    for mcporter (no `**What it does:**` bullet; the prose paragraphs
    are out of scope). Agent_owner stays NULL since "Available to:" is
    informational, not "Only available to:"."""

    # Name comes from the H2 title's parenthetical: "AD-HOC MCP ACCESS (mcporter)".
    m = re.search(r"\(([^)]+)\)", h2_title)
    if m is None:
        log.warning(
            "manifest.mcporter_h2_no_parenthetical title=%r", h2_title
        )
        return None
    name = m.group(1).strip()

    parsed: dict[str, str | None] = {
        "transport": None,
        "auth": None,
        "agent_owner": None,
    }
    status_word: str | None = None

    for line in body_lines:
        bullet_match = _BULLET_RE.match(line.strip())
        if bullet_match is None:
            continue
        key = bullet_match.group("key").strip().lower()
        value = bullet_match.group("value").strip()
        if key == "status":
            status = parse_compound_status_line(value)
            status_word = status.pop("lifecycle_status_word", None)
            for dest, sub_val in status.items():
                parsed[dest] = sub_val
            continue
        if key in _BULLET_KEY_INFORMATIONAL:
            continue
        # Other recognized bullets (in case future operator edits add them).
        dest = _BULLET_KEY_DESTINATIONS.get(key)
        if dest is not None:
            parsed[dest] = value

    if status_word is None:
        log.warning("manifest.missing_status name=%r", name)
        lifecycle_state = "discovered"
    else:
        lifecycle_state = _status_to_lifecycle(status_word)
    is_active = lifecycle_state == "loaded-on-boot"

    return ManifestRow(
        name=_norm_strip(name) or "",
        slug=slugify(name),
        tool_type="cli",
        description=None,  # mcporter source uses prose, not a bullet
        lifecycle_state=lifecycle_state,
        is_active=is_active,
        is_in_manifest=True,
        agent_owner=_norm_agent_owner_first_word(parsed["agent_owner"]),
        best_for=None,
        limitation=None,
        prefix=None,
        transport=_norm_strip(parsed["transport"]),
        auth=_norm_lower_strip(parsed["auth"]),
    )


def _parse_worker_section(
    body_lines: list[str],
) -> Iterator[tuple[str, list[str]]]:
    """Yield (agent_codename, tool_names_referenced) per H3 block in the
    worker section. Each H3 like `### Scout (Content Prep) — 46 tools`
    is followed by a list of bullets, the first of which is the inline
    `Firefox DevTools (24) + Memory (8) + ...` tool reference. Other
    bullets (Memory at:, Skills at:) are informational."""

    current_agent: str | None = None
    current_tools: list[str] = []

    for line in body_lines:
        stripped = line.strip()
        h3_match = _H3_RE.match(stripped) if stripped.startswith("###") else None
        if h3_match is not None:
            # Flush prior agent.
            if current_agent is not None:
                yield current_agent, current_tools
            current_tools = []
            agent_match = _H3_WORKER_RE.match(h3_match.group("title").strip())
            current_agent = (
                agent_match.group("agent").lower()
                if agent_match is not None
                else None
            )
            continue
        tool_list_match = _WORKER_TOOL_LIST_RE.match(line)
        if tool_list_match is not None and current_agent is not None:
            for raw in tool_list_match.group("tools").split("+"):
                raw = raw.strip()
                item = _WORKER_TOOL_ITEM_RE.match(raw)
                if item is not None:
                    current_tools.append(item.group("name").strip())
    if current_agent is not None:
        yield current_agent, current_tools


# ---- Section walker ------------------------------------------------------


def _iter_h2_sections(text: str) -> Iterator[tuple[str, str]]:
    """Yield (h2_title, body_text) per H2 section in the source. Body
    extends until the next H2 or end-of-file."""
    matches = list(_H2_RE.finditer(text))
    for i, m in enumerate(matches):
        title = m.group("title").strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        yield title, text[body_start:body_end]


def _iter_h3_blocks(
    section_body: str,
) -> Iterator[tuple[str, list[str]]]:
    """Within a section body, yield (h3_title, body_lines) per H3 block.
    Body lines extend until the next H3 or end-of-section."""
    h3_matches = list(_H3_RE.finditer(section_body))
    for i, m in enumerate(h3_matches):
        title = m.group("title").strip()
        body_start = m.end()
        body_end = (
            h3_matches[i + 1].start()
            if i + 1 < len(h3_matches)
            else len(section_body)
        )
        body_lines = section_body[body_start:body_end].splitlines()
        yield title, body_lines


# ---- Public entry points -------------------------------------------------


def iter_manifest_rows(
    source_text: str,
) -> tuple[list[ManifestRow], list[tuple[str, list[str]]], ManifestIngestStats]:
    """Parse `source_text` and return (rows, worker_xrefs, partial_stats).

    `rows` lists every parsed tool entry (Alfred MCPs + mcporter + buildables);
    `worker_xrefs` lists per-agent tool-name references found in the worker
    section; `partial_stats` carries `sections_parsed` / `sections_skipped`
    counts. The caller resolves cross-references against `rows` and
    completes the stats."""

    rows: list[ManifestRow] = []
    worker_xrefs: list[tuple[str, list[str]]] = []
    stats = ManifestIngestStats()

    for h2_title, body in _iter_h2_sections(source_text):
        section_kind = _classify_h2(h2_title)
        if section_kind == _SECTION_PASSTHROUGH:
            stats.sections_skipped += 1
            continue
        stats.sections_parsed += 1

        if section_kind == _SECTION_ALFRED:
            for h3_title, h3_body in _iter_h3_blocks(body):
                row = _parse_h3_block(h3_title, h3_body, _SECTION_ALFRED)
                if row is not None:
                    rows.append(row)
        elif section_kind == _SECTION_BUILDABLE:
            for h3_title, h3_body in _iter_h3_blocks(body):
                row = _parse_h3_block(h3_title, h3_body, _SECTION_BUILDABLE)
                if row is not None:
                    rows.append(row)
        elif section_kind == _SECTION_MCPORTER:
            # H2-as-entry path: parse the H2 body directly (paragraph-form
            # bullets). Also handle the synthetic-section round-trip case
            # where the exporter has emitted an H3 under this H2 — detect
            # by checking for H3 in body.
            if _H3_RE.search(body):
                for h3_title, h3_body in _iter_h3_blocks(body):
                    row = _parse_h3_block(
                        h3_title, h3_body, _SECTION_MCPORTER
                    )
                    if row is not None:
                        rows.append(row)
            else:
                body_lines = body.splitlines()
                row = _parse_mcporter_h2(h2_title, body_lines)
                if row is not None:
                    rows.append(row)
        elif section_kind == _SECTION_WORKER:
            for agent, tool_names in _parse_worker_section(body.splitlines()):
                worker_xrefs.append((agent, tool_names))

    return rows, worker_xrefs, stats


def resolve_cross_references(
    rows: list[ManifestRow],
    xrefs: list[tuple[str, list[str]]],
    stats: ManifestIngestStats,
) -> None:
    """For each worker cross-reference, look up the tool by name in `rows`.
    Found → increment `cross_references_resolved` (per Decision 4a we do
    NOT mutate agent_owner). Not found → WARN log + increment
    `cross_references_skipped` (worker-only tool with no Alfred H3)."""

    by_name = {r.name.lower(): r for r in rows}
    for agent, tool_names in xrefs:
        for tool_name in tool_names:
            if tool_name.lower() in by_name:
                stats.cross_references_resolved += 1
            else:
                log.warning(
                    "manifest.worker_only_reference agent=%s tool=%r "
                    "(no Alfred H3 — operator should add a proper entry)",
                    agent, tool_name,
                )
                stats.cross_references_skipped += 1


# ---- Exporter ------------------------------------------------------------


_LIFECYCLE_TO_STATUS: dict[str, str] = {
    "loaded-on-boot": "ACTIVE",
    "pending-decision": "NOT YET BUILT",
    "discovered": "DISCOVERED",
    "pending": "PENDING",
    "used": "USED",
    "retired": "RETIRED",
}


def _emit_h3_block(row: ManifestRow, section_kind: str) -> str:
    """Emit a canonical H3 block for `row`. Bullet order: Status → What it
    does → Best for → Limitation → Only available to → Prefix. Compound
    Status segments emitted in canonical order: status → Transport → Auth.

    The exporter denormalizes a couple of fields for human readability:
      - agent_owner: capitalize first letter (alfred → Alfred)
      - prefix: re-add surrounding backticks
    The parser re-normalizes these on round-trip, so equivalence holds."""

    if section_kind == _SECTION_ALFRED:
        title_line = f"### MCP Server: {row.name}"
        what_it_does_key = "What it does"
    elif section_kind == _SECTION_BUILDABLE:
        title_line = f"### {row.name}"
        what_it_does_key = "What it would do"
    elif section_kind == _SECTION_MCPORTER:
        title_line = f"### {row.name}"
        what_it_does_key = "What it does"
    else:
        raise ValueError(f"unknown section_kind: {section_kind!r}")

    status_word = _LIFECYCLE_TO_STATUS.get(
        row.lifecycle_state, row.lifecycle_state.upper()
    )
    status_segments = [status_word]
    if row.transport:
        status_segments.append(f"Transport: {row.transport}")
    if row.auth:
        status_segments.append(f"Auth: {row.auth}")

    lines = [title_line, f"- **Status:** {' | '.join(status_segments)}"]
    if row.description:
        lines.append(f"- **{what_it_does_key}:** {row.description}")
    if row.best_for:
        lines.append(f"- **Best for:** {row.best_for}")
    if row.limitation:
        lines.append(f"- **Limitation:** {row.limitation}")
    if row.agent_owner:
        lines.append(f"- **Only available to:** {row.agent_owner.capitalize()}")
    if row.prefix:
        lines.append(f"- **Prefix:** `{row.prefix}`")
    return "\n".join(lines)


def dump_manifest(rows: list[ManifestRow]) -> str:
    """Render a list of ManifestRows as canonical manifest markdown.
    Groups rows by section (alfred → mcporter → buildable); within each
    section, rows emit in input order. The output is parseable by
    `iter_manifest_rows()` and yields rows that satisfy `equivalent()`
    against the originals.

    Bucketing: `tool_type='mcp'` → ALFRED; `tool_type='cli'` → AD-HOC
    (the mcporter-style ad-hoc CLI bucket); everything else (including
    `tool_type=None` from buildables AND from the unknown-status
    fallback path) → BUILDABLE. The buildable bucket is intentionally
    catch-all so every parsed row round-trips through the exporter."""

    alfred = [r for r in rows if r.tool_type == "mcp"]
    mcporter = [r for r in rows if r.tool_type == "cli"]
    buildables = [r for r in rows if r.tool_type not in ("mcp", "cli")]

    parts: list[str] = []
    if alfred:
        parts.append("## ACTIVE CAPABILITIES — ALFRED")
        parts.append("")
        for r in alfred:
            parts.append(_emit_h3_block(r, _SECTION_ALFRED))
            parts.append("")
    if mcporter:
        parts.append("## AD-HOC MCP ACCESS")
        parts.append("")
        for r in mcporter:
            parts.append(_emit_h3_block(r, _SECTION_MCPORTER))
            parts.append("")
    if buildables:
        parts.append("## BUILDABLE (Custom Capabilities Needed)")
        parts.append("")
        for r in buildables:
            parts.append(_emit_h3_block(r, _SECTION_BUILDABLE))
            parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def dump_tool_entry(row: ManifestRow) -> str:
    """Single-row convenience: emit one ManifestRow as a self-contained
    manifest excerpt (one H2 + one H3)."""
    return dump_manifest([row])


# ---- Equivalence ---------------------------------------------------------


def _normalize_for_equivalence(row: ManifestRow) -> ManifestRow:
    """Apply the Category-I normalizations to `row`. Idempotent (re-
    applying yields the same row), so safe to invoke on already-parsed
    rows as a safety net during round-trip equivalence checks.

    The parser already applies these normalizations at parse time, so
    calling _normalize_for_equivalence on a parsed row is a no-op. The
    function is load-bearing for tests that construct ManifestRow
    directly without going through the parser."""

    name_norm = _norm_strip(row.name) or ""
    return ManifestRow(
        name=name_norm,
        # Re-derive slug from the normalized name so direct-constructed
        # ManifestRows (in tests) compare equivalent to parsed rows even
        # if the test-builder didn't run slugify itself.
        slug=slugify(name_norm) if name_norm else row.slug,
        tool_type=row.tool_type,
        description=_norm_prose(row.description),
        lifecycle_state=row.lifecycle_state,
        is_active=row.is_active,
        is_in_manifest=row.is_in_manifest,
        agent_owner=_norm_lower_strip(row.agent_owner),
        best_for=_norm_prose(row.best_for),
        limitation=_norm_prose(row.limitation),
        prefix=_norm_prefix(row.prefix),
        transport=_norm_strip(row.transport),
        auth=_norm_lower_strip(row.auth),
    )


def equivalent(left: ManifestRow, right: ManifestRow) -> bool:
    """Two ManifestRows are equivalent under round-trip if, after
    Category-I normalization, every Category-II field matches byte-equal.

    Category II fields: name, slug, tool_type, description, lifecycle_state,
    is_active, is_in_manifest, agent_owner, best_for, limitation, prefix,
    transport, auth.

    Category I normalizations (idempotent):
      - whitespace strip on name, transport, agent_owner, auth
      - whitespace collapse on description, best_for, limitation
      - lowercase on agent_owner, auth
      - backtick strip + whitespace strip on prefix

    Category III fields are not present on ManifestRow at all — they
    were dropped at parse time."""

    left_n = _normalize_for_equivalence(left)
    right_n = _normalize_for_equivalence(right)
    return left_n == right_n


# ---- DB upsert -----------------------------------------------------------


def ingest_manifest(source: Path, session: Session) -> ManifestIngestStats:
    """Read `source`, parse rows, resolve cross-references, upsert into DB,
    return stats. Idempotent: upsert by slug; descriptive fields refreshed
    from source on re-run; operator-managed lifecycle fields preserved on
    existing rows (lifecycle_state if moved away from `discovered`;
    succeeded_by always preserved — parser never sets it)."""

    if not source.exists():
        stats = ManifestIngestStats()
        stats.errors.append((str(source), "source file not found"))
        return stats

    text = source.read_text(encoding="utf-8")
    rows, xrefs, stats = iter_manifest_rows(text)
    resolve_cross_references(rows, xrefs, stats)

    seen_slugs: set[str] = set()
    for row in rows:
        if row.slug in seen_slugs:
            stats.errors.append((row.slug, "duplicate slug in source"))
            continue
        seen_slugs.add(row.slug)

        existing = session.query(Tool).filter_by(slug=row.slug).one_or_none()
        if existing is None:
            session.add(
                Tool(
                    slug=row.slug,
                    name=row.name,
                    description=row.description,
                    tool_type=row.tool_type,
                    is_in_manifest=row.is_in_manifest,
                    is_active=row.is_active,
                    lifecycle_state=row.lifecycle_state,
                    agent_owner=row.agent_owner,
                    best_for=row.best_for,
                    limitation=row.limitation,
                    prefix=row.prefix,
                    transport=row.transport,
                    auth=row.auth,
                )
            )
            stats.tools_created += 1
        else:
            # Refresh descriptive fields.
            existing.name = row.name
            if row.description is not None:
                existing.description = row.description
            if row.tool_type is not None:
                existing.tool_type = row.tool_type
            existing.agent_owner = row.agent_owner
            existing.best_for = row.best_for
            existing.limitation = row.limitation
            existing.prefix = row.prefix
            existing.transport = row.transport
            existing.auth = row.auth
            # Preserve operator-managed lifecycle_state if it has moved
            # away from `discovered`. Allow refresh only when both source
            # and DB say `discovered` (no operator decision yet).
            if existing.lifecycle_state == "discovered":
                existing.lifecycle_state = row.lifecycle_state
                existing.is_active = row.is_active
            # succeeded_by is never touched by the parser.
            stats.tools_updated += 1

    session.commit()
    return stats


# ---- DB export -----------------------------------------------------------


def tool_to_manifest_row(tool: Tool) -> ManifestRow:
    """Reconstruct a ManifestRow from a persisted Tool row — the inverse
    of the row construction in `ingest_manifest`.

    The DB stores parser-canonical values verbatim (the parser
    normalizes at parse time; `ingest_manifest` writes without
    re-touching), so the reconstruction is a plain field copy: no
    re-normalization is needed here, and `equivalent()` re-applies the
    idempotent Category-I normalizations on comparison regardless.

    Carries exactly the ManifestRow field set — the Tool columns the
    parser populates. The remaining Tool columns (id, pack_id, category,
    install_method, path, ambient_loading, succeeded_by, created_at,
    updated_at) are DB-managed or out of the manifest's scope and are
    not represented on ManifestRow. `succeeded_by` in particular is
    never a manifest field (the parser never sets it; D79) — it is
    intentionally absent from the round-trip.
    """
    return ManifestRow(
        name=tool.name,
        slug=tool.slug,
        tool_type=tool.tool_type,
        description=tool.description,
        lifecycle_state=tool.lifecycle_state,
        is_active=tool.is_active,
        is_in_manifest=tool.is_in_manifest,
        agent_owner=tool.agent_owner,
        best_for=tool.best_for,
        limitation=tool.limitation,
        prefix=tool.prefix,
        transport=tool.transport,
        auth=tool.auth,
    )


def export_manifest(session: Session) -> str:
    """Render the SQLite catalog back to canonical manifest markdown —
    the DB-grounded inverse of `ingest_manifest`.

    Reads every `Tool` row with `is_in_manifest=True` (the rows that
    originate from a TOOL-MANIFEST.md ingest; catalog/skills-sourced
    rows and operator-added rows that never appeared in a manifest are
    excluded), reconstructs ManifestRows, and emits markdown via
    `dump_manifest`. Rows are ordered by `Tool.id` for deterministic
    output.

    The emitted markdown is parseable by `iter_manifest_rows()` and
    round-trips under `equivalent()`. It is NOT a byte-faithful copy of
    a source manifest: only the tool-bearing sections (ALFRED / AD-HOC /
    BUILDABLE) are emitted — the worker cross-reference section and the
    passthrough H2s (FLEET OVERVIEW, SHARED INFRASTRUCTURE, How to Use
    This Manifest, etc.) carry no DB rows and are intentionally not
    reconstructed. Round-trip fidelity is asserted over the tool rows
    via `equivalent()`, not by a raw-text diff of the whole file.
    """
    rows = [
        tool_to_manifest_row(tool)
        for tool in (
            session.query(Tool)
            .filter_by(is_in_manifest=True)
            .order_by(Tool.id)
            .all()
        )
    ]
    return dump_manifest(rows)
