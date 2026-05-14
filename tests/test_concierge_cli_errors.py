"""Direct unit tests for `ServiceError.user_message` branch logic.

The integration suite in `test_concierge_cli.py` hits the
structured-dict and string-detail paths. The null-detail and
unknown-dict-fallback paths are easier to assert directly — and
the branch logic in `ServiceError.user_message` is the kind of
pure-function code that benefits from a tight, branch-by-branch
test surface so a regression surfaces immediately.
"""
from __future__ import annotations

import pytest

from concierge_cli.errors import ServiceError


@pytest.mark.parametrize(
    "status,detail,expected_message",
    [
        pytest.param(
            502,
            {"error": "recommendation_parse_failed", "message": "bad parse"},
            "concierge: service returned 502 recommendation_parse_failed: bad parse",
            id="structured_dict",
        ),
        pytest.param(
            500,
            "internal server error",
            "concierge: service returned 500: internal server error",
            id="string_detail",
        ),
        pytest.param(
            503,
            None,
            "concierge: service returned 503",
            id="null_detail",
        ),
        pytest.param(
            502,
            {"wat": "no error key"},
            'concierge: service returned 502: {"wat": "no error key"}',
            id="unknown_dict_fallback",
        ),
    ],
)
def test_service_error_user_message_branches(status, detail, expected_message):
    err = ServiceError(status=status, detail=detail)
    assert err.user_message == expected_message
