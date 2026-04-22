"""Claude-Code-framed adapter preamble for the concierge_recommend
gap-report. **Not a Class-1 prompt-fragment extract.**

## Why this file is not tracked in SKILL_FRAGMENT_SYNC_LOG.md

A Class-1 `prompt-fragment` (per DECISIONS `[2026-04-21 05:50]`) is a
verbatim byte-for-byte copy of a source skill file, with OpenClaw
coupling preserved, composed into an Opus system prompt. The
five-member set (X3 / X4 / X6 / X7-A / X8) closed at the X8 extract
on 2026-04-22 — future Class-1 work is re-sync activity on those
five fragments, not net-new extractions.

This module is different in kind. It is **adapter-authored**, not
extracted: it deliberately

1. substitutes OpenClaw fleet framing with Claude Code single-agent
   framing (see the substitution table in the N12 architectural
   pause), so the wording fits the actual consumer context,
2. condenses X8's six sections into four points oriented around
   the Claude Code meta-tool surface (`concierge_list_active`,
   `concierge_request_tool`, `concierge_recommend`),
3. adds Concierge-adapter-specific meta-tool names that do not
   exist in the source.

The Class-1 verbatim-invariant therefore does not apply here.
Adding this module to the sync-log's Current-prompt-fragments table
would wrongly imply that the Class-1 re-sync protocol (byte-for-byte
drift-check against source) governs it — it does not.

## What drift detection does apply

A source-cross-check test (see
`tests/test_meta_tools_gap_preamble.py::test_source_cross_check_against_x8`)
asserts that X8's anchor phrases (`## Capability Honesty`,
`## Planning Discipline`, `## Workaround Transparency`, etc.) still
appear in the X8 source fragment. If a future re-sync of X8
re-authors those anchor wordings, this test fails and flags that
the preamble may need a joint update. The check is the same pattern
as the python-constants source-cross-check (X7-B) — anchor-phrase
presence, not byte-for-byte parity.

## Consumer

This preamble is consumed **only** by the gap-report generator in
`adapters/claude_code/meta_tools/gap_report.py`. It is not directly
rendered into the `concierge_recommend` result payload (per N12
proposal Q2 answer: hidden-informant, not visible footer). Its
phrasing informs the "Suggested next action" section's wording, so
behavioral guidance is baked into the gap-report's voice rather
than copy-pasted as a trailing block.

## Verbatim X8 exposure to the session

Deferred per N12 proposal Q4 answer. Future X-slot may advertise
X8 via MCP `resources/list` + `resources/read` under URI
`concierge://prompts/behavioral-rules.md`. Verbatim X8 is already
available on disk in `core/prompts/soul_delta.py` for any future
consumer that needs it; this preamble is the V1 adapter-side
behavioral-voice surface.
"""
from __future__ import annotations


CLAUDE_CODE_GAP_PREAMBLE = """\
# Concierge — Claude Code adapter context

You are operating in a Claude Code session. Concierge is the tool-awareness
layer assisting you; it is not your personality or your replacement.

Behavioral posture (mirrors the SOUL-delta rules, framed for this
single-agent context):

- **Capability honesty.** When your current tool surface cannot meet a task,
  say so rather than silently degrading quality. Use `concierge_list_active`
  to check the Concierge catalog before concluding a gap exists.
- **Planning discipline.** For multi-step tasks, decompose before executing.
  If a step has no matching tool, a Concierge gap-report will surface it in
  the `concierge_recommend` result — act on it in the moment, not after
  finishing the task.
- **Do not block on approval.** Filing a `concierge_request_tool` call
  continues the current task with existing tools. The operator reviews
  pending requests asynchronously; blocking wastes their time and yours.
- **Workaround transparency.** If you use a workaround, name it as a
  workaround in your response. Concise honesty beats performative completion.
"""
