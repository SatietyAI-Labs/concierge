"""Tests for CLAUDE_CODE_GAP_PREAMBLE — the Claude-Code-adapter
behavioral-voice constant consumed by the N12 gap-report generator.

Not a Class-1 prompt-fragment; see `gap_preamble.py` module docstring
for why. Drift detection is anchor-phrase cross-check against X8's
source fragment, not byte-for-byte parity.
"""
from __future__ import annotations

from core.prompts import TOOL_AWARENESS_BEHAVIORAL_RULES__FROM_SOUL_DELTA_MD
from adapters.claude_code.meta_tools.gap_preamble import (
    CLAUDE_CODE_GAP_PREAMBLE,
)


def test_nonempty_string():
    assert isinstance(CLAUDE_CODE_GAP_PREAMBLE, str)
    assert len(CLAUDE_CODE_GAP_PREAMBLE) > 0


def test_under_2kb():
    """Compactness guard. N12 proposal specified ~700 bytes aspiration
    with a 2KB soft cap. Tripping this limit signals accidental
    bloat that should be caught before bleeding into result-payload
    tests downstream.
    """
    assert len(CLAUDE_CODE_GAP_PREAMBLE) < 2048


def test_substitutes_fleet_framing():
    """OpenClaw-specific framing must NOT survive into the Claude-Code
    adapter preamble. Per the N12 substitution table.
    """
    forbidden = [
        "Alfred",
        "Scout",
        "Dispatch",
        "Radar",
        "Bridge",
        "ClawHub",
        "bridge config",
        "~/.satiety-pipeline",
        "~/.openclaw",
        "WhatsApp",
        "MailerLite",
        "ElevenLabs",
        "Firefox",
    ]
    for term in forbidden:
        assert term not in CLAUDE_CODE_GAP_PREAMBLE, (
            f"OpenClaw coupling term '{term}' leaked into the "
            "Claude-Code-adapter preamble. The preamble is supposed "
            "to be a DISTILLATION of X8 with fleet framing removed."
        )


def test_substitutes_fleet_framing_in_phrases():
    """Fleet-framing phrases (not just proper nouns) must also be
    absent. The preamble is single-agent-framed by design.
    """
    # The lone-word "fleet" must not appear. The word "agent" is
    # permitted — the preamble does refer to "the agent in this
    # session" per the single-agent framing.
    assert "the fleet" not in CLAUDE_CODE_GAP_PREAMBLE.lower()
    assert "another agent" not in CLAUDE_CODE_GAP_PREAMBLE.lower()
    assert "multiple agents" not in CLAUDE_CODE_GAP_PREAMBLE.lower()
    assert "handoff points" not in CLAUDE_CODE_GAP_PREAMBLE.lower()


def test_uses_claude_code_terminology():
    """The preamble should reference the Concierge meta-tool surface
    it governs (`concierge_request_tool`, `concierge_list_active`)
    so the substitution is constructive, not merely deletion.
    """
    assert "concierge_request_tool" in CLAUDE_CODE_GAP_PREAMBLE
    assert "concierge_list_active" in CLAUDE_CODE_GAP_PREAMBLE
    assert "Claude Code" in CLAUDE_CODE_GAP_PREAMBLE


def test_references_x8_key_concepts():
    """Anchor phrases — the preamble's FOUR distilled points should
    mirror X8's SIX sections in spirit. Assertion is on concept
    presence (substring match on the bolded section-heading nouns),
    not on verbatim reproduction.
    """
    text = CLAUDE_CODE_GAP_PREAMBLE
    assert "Capability honesty" in text
    assert "Planning discipline" in text
    assert "Workaround transparency" in text
    # "Do not block on approval" — the Concierge-adapter reframing of
    # X8's "Requesting Capabilities" section. Exact wording; the test
    # shape flags a re-author that strays from the proposed voice.
    assert "Do not block on approval" in text


def test_source_cross_check_against_x8():
    """Drift detection — if X8 is re-synced with re-authored section
    headings, this preamble likely needs a joint update. The anchor
    phrases checked here are the ones the preamble's distillation
    was authored to mirror; a source edit that changes them is the
    signal that the preamble's voice has drifted from its source.

    Mirrors the `python-constants` source-cross-check pattern
    established by X7-B (`test_promotion_criteria_phrase_in_source`).
    """
    x8 = TOOL_AWARENESS_BEHAVIORAL_RULES__FROM_SOUL_DELTA_MD
    # The six X8 section headings must all exist in the source
    # fragment at check time; if any are re-authored, the preamble's
    # distillation needs re-review.
    assert "## Capability Honesty" in x8
    assert "## Planning Discipline" in x8
    assert "## Feedback and Learning" in x8
    assert "## Requesting Capabilities" in x8
    assert "## Workaround Transparency" in x8
    assert "## Tool Concierge" in x8
