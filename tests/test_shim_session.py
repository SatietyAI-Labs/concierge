"""Tests for adapters.claude_code.session — shim-lifetime session id.

Fix Day 4 Task 6: one UUID4 per shim process, exposed as
`SHIM_SESSION_ID` at module import time. Meta-tool handlers read
the attribute (not a captured reference) so tests can monkeypatch
the value for determinism.
"""
from __future__ import annotations

import re
import uuid

from adapters.claude_code import session as shim_session


class TestShimSessionId:
    def test_is_non_empty_string(self):
        assert isinstance(shim_session.SHIM_SESSION_ID, str)
        assert shim_session.SHIM_SESSION_ID

    def test_is_valid_uuid4_shape(self):
        """UUID4 canonical form: 8-4-4-4-12 hex with '4' in version
        position. Regression guard if the module is ever refactored
        to use a different id-generation strategy.
        """
        pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-"
            r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        )
        assert pattern.match(shim_session.SHIM_SESSION_ID)
        # UUID parser also accepts it — double-check.
        parsed = uuid.UUID(shim_session.SHIM_SESSION_ID)
        assert parsed.version == 4

    def test_monkeypatchable_for_tests(self, monkeypatch):
        """Handlers read via attribute lookup at call time, so test
        code can substitute a deterministic value. This is the shape
        that test_meta_tools_recommend uses to pin session_id in
        integration-style assertions.
        """
        monkeypatch.setattr(
            shim_session, "SHIM_SESSION_ID", "deterministic-test-id"
        )
        assert shim_session.SHIM_SESSION_ID == "deterministic-test-id"
