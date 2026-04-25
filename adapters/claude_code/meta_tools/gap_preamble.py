"""Claude-Code-framed adapter preamble for the concierge_recommend
gap-report.

This module is **adapter-authored**, not extracted. It is the
Claude-Code-single-agent-framed condensed mirror of the X8 SOUL-
delta behavioral rules (`core/prompts/soul_delta.py`). It deliberately

1. substitutes multi-agent fleet framing with Claude Code single-
   agent framing, so the wording fits the actual consumer context,
2. condenses X8's six sections into four points oriented around
   the Claude Code meta-tool surface (`concierge_list_active`,
   `concierge_request_tool`, `concierge_recommend`),
3. adds Concierge-adapter-specific meta-tool names that do not
   exist in the source.

(During the v3 build period this module was explicitly outside the
EXTRACT-invariant scope — see DECISIONS `[2026-04-21 05:50]` and
its retirement at `[2026-04-29 Day 8]`. Both the EXTRACT invariant
and the Class-1 / non-Class-1 distinction are now historical.)

## Drift cross-check with X8

A source-cross-check test (see
`tests/test_meta_tools_gap_preamble.py::test_source_cross_check_against_x8`)
asserts that X8's anchor phrases (`## Capability Honesty`,
`## Planning Discipline`, `## Workaround Transparency`, etc.) still
appear in the X8 source fragment. If a future edit of X8
re-authors those anchor wordings, this test fails and flags that
the preamble may need a joint update.

## Consumer

This preamble is consumed **only** by the gap-report generator in
`adapters/claude_code/meta_tools/gap_report.py`. It is not directly
rendered into the `concierge_recommend` result payload (per N12
proposal Q2 answer: hidden-informant, not visible footer). Its
phrasing informs the "Suggested next action" section's wording, so
behavioral guidance is baked into the gap-report's voice rather
than copy-pasted as a trailing block.

## Verbatim X8 exposure to the session

Implemented in Fix Day 4 Task 2 (per DECISIONS `[2026-04-23]` —
Push channel reframed as narration-as-push, pattern 2). The X8
body ships verbatim at `concierge://prompts/behavioral-rules.md`
via the MCP `resources/list` + `resources/read` protocol wired in
`adapters/claude_code/resources.py`. This condensed gap-preamble
remains the adapter-side behavioral-voice surface consumed by the
gap-report generator; the two coexist deliberately — this file is
the action-framed condensed version, X8 is the verbatim source,
and sessions reading resources see both together.
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
