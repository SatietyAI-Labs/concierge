"""Tests for `core.lifecycle_policy` — the python-constants extract from
tool-lifecycle/SKILL.md (X7-B).

Companion to `tests/test_prompts.py::TestToolLifecycleWeeklyReviewFragment`
(X7-A, the prompt-fragment side of the same source).

Test classes cover four concerns:

1. **Import + type shape** — constants resolve, have the expected
   types, and collections use immutable containers (frozenset, tuple).
2. **Structural consistency** — status transitions reference only
   declared status values; content-field tuple is ordered as source
   specifies.
3. **Value correctness** — numeric thresholds match the source's
   stated values (5, 30, 90, 7).
4. **Source-cross-check (drift detection)** — the distinctive literal
   phrases in the source that anchor each constant's value still
   appear in the live source file. Catches the drift case where
   someone edits source prose ("Used 5+ times in the last 30 days"
   → "Used 6+ times in the last 14 days") without re-authoring the
   Python constants.

The source-cross-check is the structural equivalent of the prompt-
fragment drift check, adapted for re-authored-value extracts instead
of verbatim-body extracts.
"""

from pathlib import Path

import pytest

from core.lifecycle_policy import (
    DEMOTION_INACTIVITY_DAYS,
    PROMOTION_MIN_USES,
    PROMOTION_WINDOW_DAYS,
    STALE_PENDING_DAYS,
    TOOL_SELECTION_CONTENT_FIELDS,
    TOOL_SELECTION_MEMORY_TAG,
    TOOL_SELECTION_STATUS_TRANSITIONS,
    TOOL_SELECTION_STATUS_VALUES,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_RELPATH = "_legacy/openclaw-workspace/skills/tool-lifecycle/SKILL.md"


def _source_text_or_skip() -> str:
    """Load the live source file, or skip gracefully if `_legacy/`
    symlinks aren't accessible on this clone.
    """
    path = REPO_ROOT / SOURCE_RELPATH
    if not path.exists():
        pytest.skip(
            f"{SOURCE_RELPATH} not accessible — source-cross-check "
            "requires the _legacy/ symlink tree"
        )
    return path.read_text(encoding="utf-8")


class TestTypeShape:
    """Import resolution + type assertions."""

    def test_memory_tag_is_nonempty_string(self):
        assert isinstance(TOOL_SELECTION_MEMORY_TAG, str)
        assert TOOL_SELECTION_MEMORY_TAG

    def test_status_values_is_frozenset_of_strings(self):
        assert isinstance(TOOL_SELECTION_STATUS_VALUES, frozenset)
        assert len(TOOL_SELECTION_STATUS_VALUES) == 6
        assert all(isinstance(v, str) for v in TOOL_SELECTION_STATUS_VALUES)

    def test_status_transitions_is_dict_of_frozensets(self):
        assert isinstance(TOOL_SELECTION_STATUS_TRANSITIONS, dict)
        for from_status, to_set in TOOL_SELECTION_STATUS_TRANSITIONS.items():
            assert isinstance(from_status, str)
            assert isinstance(to_set, frozenset)
            assert all(isinstance(v, str) for v in to_set)

    def test_content_fields_is_nonempty_tuple(self):
        assert isinstance(TOOL_SELECTION_CONTENT_FIELDS, tuple)
        assert len(TOOL_SELECTION_CONTENT_FIELDS) == 6
        assert all(isinstance(f, str) for f in TOOL_SELECTION_CONTENT_FIELDS)

    def test_thresholds_are_positive_ints(self):
        for name, value in [
            ("PROMOTION_MIN_USES", PROMOTION_MIN_USES),
            ("PROMOTION_WINDOW_DAYS", PROMOTION_WINDOW_DAYS),
            ("DEMOTION_INACTIVITY_DAYS", DEMOTION_INACTIVITY_DAYS),
            ("STALE_PENDING_DAYS", STALE_PENDING_DAYS),
        ]:
            assert isinstance(value, int), f"{name} should be int"
            assert not isinstance(value, bool), f"{name} must not be bool"
            assert value > 0, f"{name} should be positive"


class TestStructuralConsistency:
    """Internal consistency of the extracted constants."""

    def test_status_values_contain_the_six_named(self):
        expected = {
            "pending",
            "approved",
            "installed",
            "denied",
            "failed",
            "removed",
        }
        assert TOOL_SELECTION_STATUS_VALUES == frozenset(expected)

    def test_status_transitions_reference_only_declared_status_values(self):
        """Every `from` key and every `to` element must be in the
        canonical STATUS_VALUES set. Catches typos and ensures any
        future transition addition goes through STATUS_VALUES.
        """
        for from_status, to_set in TOOL_SELECTION_STATUS_TRANSITIONS.items():
            assert from_status in TOOL_SELECTION_STATUS_VALUES, (
                f"Transition key '{from_status}' not in STATUS_VALUES"
            )
            for to_status in to_set:
                assert to_status in TOOL_SELECTION_STATUS_VALUES, (
                    f"Transition target '{from_status} -> {to_status}' "
                    "not in STATUS_VALUES"
                )

    def test_status_transitions_match_source_spec(self):
        """The four explicit transitions listed under source's
        `## Memory tagging convention` / "Updating memory entries".
        """
        expected = {
            "pending": frozenset({"approved", "denied"}),
            "approved": frozenset({"installed"}),
            "installed": frozenset({"removed"}),
        }
        assert TOOL_SELECTION_STATUS_TRANSITIONS == expected

    def test_content_fields_ordered_per_source_template(self):
        """Source's content template orders fields as
        TOOL | PATTERN | STATUS | AGENT | DATE | NOTES.
        """
        assert TOOL_SELECTION_CONTENT_FIELDS == (
            "TOOL",
            "PATTERN",
            "STATUS",
            "AGENT",
            "DATE",
            "NOTES",
        )

    def test_threshold_values(self):
        """Lock in the numeric values so a silent edit in
        `core/lifecycle_policy.py` fails a test rather than going unnoticed.
        """
        assert PROMOTION_MIN_USES == 5
        assert PROMOTION_WINDOW_DAYS == 30
        assert DEMOTION_INACTIVITY_DAYS == 90
        assert STALE_PENDING_DAYS == 7


class TestSourceCrossCheck:
    """Drift detection — assert the source prose still contains the
    literal phrases that anchor each constant's value. If source is
    edited (e.g. "5+ times" → "6+ times") without re-authoring
    `core/lifecycle_policy.py`, these tests fail and force a joint re-sync
    of the Python constants and X7-A's prompt fragment.
    """

    def test_memory_tag_literal_appears_in_source(self):
        source = _source_text_or_skip()
        assert (
            f"tag: {TOOL_SELECTION_MEMORY_TAG}" in source
            or f"`{TOOL_SELECTION_MEMORY_TAG}`" in source
        ), f"Memory tag literal '{TOOL_SELECTION_MEMORY_TAG}' not found in source"

    def test_all_status_values_appear_in_source_status_list(self):
        """Source lists each status value as a bullet under "Status
        values:" with a backticked name."""
        source = _source_text_or_skip()
        for status in TOOL_SELECTION_STATUS_VALUES:
            assert f"`{status}`" in source, (
                f"Status value '{status}' not found as a backticked token "
                "in source"
            )

    def test_content_fields_appear_in_source_template(self):
        """Source's content template is one line containing each field
        name followed by ": <...>". Check each field is present."""
        source = _source_text_or_skip()
        for field in TOOL_SELECTION_CONTENT_FIELDS:
            assert f"{field}: <" in source, (
                f"Content field '{field}: <...>' not found in source template"
            )

    def test_promotion_criteria_phrase_in_source(self):
        """Anchors PROMOTION_MIN_USES and PROMOTION_WINDOW_DAYS."""
        source = _source_text_or_skip()
        expected_phrase = (
            f"Used {PROMOTION_MIN_USES}+ times in the last "
            f"{PROMOTION_WINDOW_DAYS} days"
        )
        assert expected_phrase in source, (
            f"Expected promotion-criteria phrase not found: '{expected_phrase}'. "
            "Either source prose has drifted or Python constants need re-sync."
        )

    def test_demotion_criteria_phrase_in_source(self):
        """Anchors DEMOTION_INACTIVITY_DAYS."""
        source = _source_text_or_skip()
        expected_phrase = f"Not used in {DEMOTION_INACTIVITY_DAYS}+ days"
        assert expected_phrase in source, (
            f"Expected demotion-criteria phrase not found: '{expected_phrase}'."
        )

    def test_stale_pending_phrase_in_source(self):
        """Anchors STALE_PENDING_DAYS."""
        source = _source_text_or_skip()
        expected_phrase = f"older than {STALE_PENDING_DAYS} days"
        assert expected_phrase in source, (
            f"Expected stale-pending phrase not found: '{expected_phrase}'."
        )

    def test_status_transition_phrases_in_source(self):
        """Source's "Updating memory entries" block lists transitions
        as `pending -> approved`-style arrows. Assert each declared
        transition appears in that form.
        """
        source = _source_text_or_skip()
        for from_status, to_set in TOOL_SELECTION_STATUS_TRANSITIONS.items():
            for to_status in to_set:
                arrow = f"{from_status} -> {to_status}"
                assert arrow in source, (
                    f"Declared transition '{arrow}' not found in source. "
                    "Either source has drifted or transitions dict needs re-sync."
                )
