"""Prompt fragment extracted from the tool-discovery skill.

See `core/prompts/tool_awareness.py` for the full conventions —
consumer compose model, OpenClaw coupling treatment, drift model,
Phase 2 target. That module is the canonical reference for the
prompt-fragment extraction pattern; this module only records the
per-fragment facts and the OpenClaw-specific coupling notes unique
to this source.

**Demo-critical:** per classification §C.5.3 and Phase E Risk 1, the
signal-table content (green/yellow/red candidate evaluation) is the
headline example of "prompt-fragment material, not reimplemented as
a Python scoring function." N6 composition + N8 smoke fixture
assertion (`csvstat` ranks above `pandas` for "analyze a CSV") hang
off this constant performing correctly inside Opus 4.7's system
prompt.

Source
------
Path (repo-relative, via symlink):
    _legacy/openclaw-workspace/skills/tool-discovery/SKILL.md
Absolute source at extract time:
    /home/satiety/.openclaw/workspace/skills/tool-discovery/SKILL.md
Source SHA-256:
    64b9b365ba2f9b66eb1832e17214d4599af426a5ba92d6b8f49919fc25a628ca
Source mtime:
    2026-04-13 20:46:25 -0700
Source bytes:
    5223

Extract
-------
Extracted:
    2026-04-21 16:25 PDT (SESSION-2026-04-21-02, item X6)
Section extracted:
    Full document body below the YAML frontmatter (source lines
    6-111). YAML `name:` / `description:` fields excluded
    (skill-loader metadata, not prompt content).
Fidelity:
    VERBATIM. No paraphrase, no reflow, no normalization. No
    backslash / triple-quote hazards in source; no escaping applied.

Constant naming
---------------
`TOOL_DISCOVERY_PROTOCOL__FROM_TOOL_DISCOVERY_SKILL` — chosen for
structural consistency with X3/X4's `{SOURCE}_PROTOCOL__FROM_{SOURCE}_*`
pattern, since this file also covers a whole-document protocol
(search → evaluate → file → follow-up). DECISIONS `[2026-04-21 05:50]`
mitigation #3 suggested `DISCOVERY_SIGNALS__FROM_TOOL_DISCOVERY_SKILL`
as an illustrative example, but that name only describes the
signal-table subsection. Choosing `PROTOCOL` to reflect the whole
extracted body. The governing requirement ("verbose on purpose so
drift is visible in grep") is satisfied either way; structural
consistency across X3/X4/X6 wins the tiebreak.

OpenClaw coupling (this fragment's specifics)
---------------------------------------------
Preserved verbatim in the constant:

- Pipeline README path: `~/.satiety-pipeline/outbox/tool-requests/
  README.md`
- Catalog path: `~/satiety-docs/TOOL-CATALOG.md`
- Catalog section names: "Installed" / "Not Installed"

Coupling footprint is the lightest of the prompt-fragment set —
worked example uses generic `pandoc` / markdown-to-PDF, no fleet
agent names, no MCP tool IDs. Consumer (N6 compose step) handles
substitution if an adapter doesn't expose those paths.
"""

TOOL_DISCOVERY_PROTOCOL__FROM_TOOL_DISCOVERY_SKILL = """\
# Tool Discovery -- Finding What You Don't Know About

## When this applies

You have a clear tool gap. You checked memory, resolved requests, the catalog, and the manifest. None had a match. Before giving up or building a workaround, spend one turn researching.

## Search strategy

Use `web_search` for initial discovery, `web_fetch` to verify details on promising candidates.

### Search patterns by domain

**CLI tools (general):**
- `"best <capability> command line tool linux"` -- broad overview
- `site:github.com awesome-<domain>` -- curated lists (awesome-csv, awesome-cli-apps, awesome-shell)
- `"<capability> vs" site:reddit.com` -- real-world comparisons from users

**Python packages:**
- `site:pypi.org <capability>` -- direct registry search
- `"pip install" <capability> CLI` -- finds packages with CLI entry points

**Node/npm packages:**
- `site:npmjs.com <capability>` -- direct registry search
- `"npx" <capability>` -- finds packages designed for one-shot use

**Rust/Go binaries (fast CLI tools):**
- `"cargo install" <capability>` or `"go install" <capability>` -- often the fastest CLI tools
- Modern replacements: fd (find), ripgrep (grep), bat (cat), eza (ls), dust (du), procs (ps), bottom (top)

**MCP servers:**
- `"mcp server" <capability>` -- general search
- `site:github.com "mcp-server" <capability>` -- GitHub repos
- `site:npmjs.com "mcp" <capability>` -- npm packages

**Data processing:**
- `"<format> processing cli"` (e.g., "csv processing cli", "json cli tool")
- `"<format> swiss army knife"` -- often finds the comprehensive tool for that format

### What makes a good search

Be specific about the capability, not the solution. Search for what you need to DO, not what you think the tool might be called.

Good: `"csv column statistics command line"` -- finds csvkit, xsv, miller
Bad: `"csvtool"` -- might miss the best options

## Evaluating candidates

After finding 2-5 candidates, filter to 1-3 by checking these signals.

### Must-have

- **Works on Ubuntu/WSL2:** Must run on your actual environment. macOS-only tools are useless here.
- **Installable without sudo (preferred):** pip --user, npm -g, single binary to ~/bin. If it needs apt/sudo, note it -- still valid but requires operator approval.
- **Actually solves the gap:** Read the README. Does it handle your specific use case, or is it adjacent?

### Strong signals (check via web_fetch on the GitHub/registry page)

| Signal | Green | Yellow | Red |
|--------|-------|--------|-----|
| GitHub stars | 1000+ | 100-999 | Under 100 |
| Last commit | Within 6 months | 6-12 months | Over 12 months |
| Downloads (npm/PyPI) | 10k+/month | 1k-10k | Under 1k |
| License | MIT, Apache 2.0, BSD | GPL, LGPL | Proprietary, SSPL, or missing |
| Dependencies | Few or none | Moderate | Pulls in heavy frameworks |
| Documentation | Clear README + examples | README only | No docs |

### Don't over-research

You are spending the operator's tokens. One search round (2-4 queries) should be enough. If nothing good surfaces, file a lower-confidence request or log to the wishlist. Don't do 15 searches for a marginal tool.

## Filing a discovery request

Use the standard template in the README at `~/.satiety-pipeline/outbox/tool-requests/README.md`. Key differences for discovery:

1. Set `Discovered: true` in the Request section
2. Fill the `Source` field: where you found it (npm registry, awesome-list URL, etc.)
3. Fill the `Evidence` field: stars, downloads, last commit, license
4. If presenting multiple candidates, put the recommended one as the main tool and list the others under Alternatives with one line each explaining the trade-off

### Example discovery request snippet

```
## Request
- **Task context:** Needed to convert markdown documentation to PDF for a client deliverable.
- **Tool suggested:** pandoc
- **Category:** text-processing
- **Install method:** apt (requires approval)
- **Discovered:** true

## Recommendation
- **Why this tool:** pandoc converts between 30+ document formats. markdown-to-PDF is its core use case. One command: pandoc input.md -o output.pdf.
- **Alternatives considered:** md-to-pdf (npm, simpler but less flexible, 800 stars), grip (GitHub-flavored preview only, no PDF export).
- **Risk/cost:** sudo for apt. Free. No security concerns.
- **Confidence:** high
- **Source:** GitHub awesome-markdown list, confirmed on pandoc.org
- **Evidence:** 36k GitHub stars, active development (last commit 3 days ago), GPL license, packaged in Ubuntu repos.
```

## After discovery

Whether the request is approved or not, update the Tool Catalog at `~/satiety-docs/TOOL-CATALOG.md`:
- If approved and installed: move from "Not Installed" to "Installed" section
- If approved but not yet installed: add to "Not Installed" with install instructions
- If denied: do not add (but the resolved request serves as the record)

This is how the catalog grows organically from real usage patterns.
"""
