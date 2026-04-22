"""Tests for core.lifecycle_store.transitions — file-side legality.

File-side vocabulary is distinct from the memory-side vocabulary
in core.lifecycle_policy. These tests pin the file-side table so a
future edit doesn't silently import the memory-side table and
introduce a spurious 'removed' transition or drop 'deferred'.
"""
from __future__ import annotations

import pytest

from core.lifecycle_policy import TOOL_SELECTION_STATUS_TRANSITIONS
from core.lifecycle_store.transitions import (
    InvalidTransitionError,
    VALID_FILE_STATUSES,
    assert_valid_transition,
)


class TestFileSideVocabulary:
    def test_file_side_includes_deferred(self):
        assert "deferred" in VALID_FILE_STATUSES

    def test_file_side_excludes_memory_only_values(self):
        """`removed` is a memory-side terminal state (post-install
        retirement); it must not appear in the file-side table.
        """
        assert "removed" not in VALID_FILE_STATUSES

    def test_file_side_and_memory_side_are_distinct(self):
        memory_side = set(TOOL_SELECTION_STATUS_TRANSITIONS.keys())
        # Memory-side doesn't know about `deferred`; file-side does.
        assert "deferred" not in memory_side
        # File-side doesn't know about `removed`; memory-side does.
        assert "removed" not in VALID_FILE_STATUSES


class TestLegalTransitions:
    def test_pending_to_approved(self):
        assert_valid_transition(current="pending", target="approved")

    def test_pending_to_denied(self):
        assert_valid_transition(current="pending", target="denied")

    def test_pending_to_deferred(self):
        assert_valid_transition(current="pending", target="deferred")

    def test_approved_to_installed(self):
        assert_valid_transition(current="approved", target="installed")

    def test_approved_to_failed(self):
        assert_valid_transition(current="approved", target="failed")

    def test_deferred_back_to_pending(self):
        assert_valid_transition(current="deferred", target="pending")


class TestIllegalTransitions:
    def test_pending_to_installed_direct_rejected(self):
        """You must go through `approved` first. Direct jump is a
        data-integrity bug (the human step was skipped).
        """
        with pytest.raises(InvalidTransitionError, match="illegal transition"):
            assert_valid_transition(current="pending", target="installed")

    def test_installed_is_terminal(self):
        with pytest.raises(InvalidTransitionError, match="terminal"):
            assert_valid_transition(current="installed", target="pending")

    def test_denied_is_terminal(self):
        with pytest.raises(InvalidTransitionError, match="terminal"):
            assert_valid_transition(current="denied", target="approved")

    def test_failed_is_terminal(self):
        with pytest.raises(InvalidTransitionError, match="terminal"):
            assert_valid_transition(current="failed", target="approved")

    def test_unknown_current_status(self):
        with pytest.raises(InvalidTransitionError, match="not a recognized"):
            assert_valid_transition(current="weird", target="pending")

    def test_unknown_target_status(self):
        with pytest.raises(InvalidTransitionError, match="not a recognized"):
            assert_valid_transition(current="pending", target="removed")  # memory-side, not file-side
