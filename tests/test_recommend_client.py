"""Regression tests for `core.recommend.client.AnthropicRecommender`.

The primary concern is the **shape of the outgoing Anthropic API
request** — specifically that we do NOT send `temperature`
(deprecated for Opus 4.7; returns 400) and DO send
`output_config={"effort": <value>}` instead. Manual verification
on 2026-04-22 surfaced the deprecation (DECISIONS
[2026-04-22 15:45]); this file's assertions are the unit-level
tripwire that catches a regression which re-introduces the
deprecated parameter.

Pattern mirrors the hardcoded-expectation regression test pattern
we adopted for the protocolVersion fix (`TestRealClaudeCodeProtocol
Version` in `tests/test_shim_e2e.py`): specific values asserted
directly, not via dynamic-constant imports, so a default-value
change forces a conscious re-verification.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.recommend.client import AnthropicClientError, AnthropicRecommender


def _mock_anthropic_response(content: str = '{"recommendations": []}'):
    """Build a MagicMock that matches the shape `client._extract_text`
    and the usage-reader expect. We set attributes rather than using
    spec= because the real Anthropic response types aren't stable
    enough to pin here.
    """
    text_block = MagicMock()
    text_block.text = content

    usage = MagicMock()
    usage.input_tokens = 1000
    usage.output_tokens = 200
    usage.cache_creation_input_tokens = 0
    usage.cache_read_input_tokens = 0

    response = MagicMock()
    response.content = [text_block]
    response.stop_reason = "end_turn"
    response.usage = usage
    response.model = "claude-opus-4-7"
    return response


class TestOutgoingRequestShape:
    """Verify the request body we hand to the Anthropic SDK matches
    what Opus 4.7 accepts. These are the regression tests that the
    2026-04-22 manual-verification finding motivated.
    """

    def test_temperature_parameter_not_sent(self):
        """Opus 4.7 returns 400 `temperature is deprecated for this
        model` when temperature is in the request. We must NOT send
        it under any circumstance.
        """
        rec = AnthropicRecommender(
            api_key="test-key",
            model="claude-opus-4-7",
            effort="xhigh",
            max_tokens=4096,
        )
        fake_sdk = MagicMock()
        fake_sdk.messages.create.return_value = _mock_anthropic_response()
        rec._sdk = fake_sdk

        rec.call(system="sys", user="user")

        # Inspect the exact kwargs passed to sdk.messages.create
        assert fake_sdk.messages.create.call_count == 1
        _args, kwargs = fake_sdk.messages.create.call_args
        assert "temperature" not in kwargs, (
            f"`temperature` must NOT be in the Anthropic request — "
            f"Opus 4.7 deprecated it (400 'temperature is deprecated "
            f"for this model'). kwargs sent: {list(kwargs.keys())}"
        )

    def test_output_config_effort_sent_with_configured_value(self):
        """The replacement tuning knob per Anthropic's migration guide
        is `output_config.effort`. Must be sent with the value from
        settings (default `xhigh` per config.py).
        """
        rec = AnthropicRecommender(
            api_key="test-key",
            model="claude-opus-4-7",
            effort="xhigh",
            max_tokens=4096,
        )
        fake_sdk = MagicMock()
        fake_sdk.messages.create.return_value = _mock_anthropic_response()
        rec._sdk = fake_sdk

        rec.call(system="sys", user="user")

        _args, kwargs = fake_sdk.messages.create.call_args
        assert "output_config" in kwargs, (
            f"`output_config` must be in the request — it carries "
            f"the `effort` value that replaced temperature. kwargs "
            f"sent: {list(kwargs.keys())}"
        )
        assert kwargs["output_config"] == {"effort": "xhigh"}, (
            f"output_config must be the TypedDict shape "
            f"{{'effort': <value>}} per anthropic.types.OutputConfigParam; "
            f"got {kwargs['output_config']!r}"
        )

    def test_effort_value_flows_from_constructor(self):
        """Configurable effort: constructor arg propagates to the
        outgoing request body so operators can override via
        CONCIERGE_RECOMMEND_EFFORT without patching the client.
        """
        for effort_value in ("low", "medium", "high", "xhigh", "max"):
            rec = AnthropicRecommender(
                api_key="test-key",
                model="claude-opus-4-7",
                effort=effort_value,
                max_tokens=4096,
            )
            fake_sdk = MagicMock()
            fake_sdk.messages.create.return_value = _mock_anthropic_response()
            rec._sdk = fake_sdk

            rec.call(system="sys", user="user")
            _args, kwargs = fake_sdk.messages.create.call_args
            assert kwargs["output_config"] == {"effort": effort_value}

    def test_model_max_tokens_system_user_still_sent(self):
        """Sanity: the core required fields are still in the request.
        Catches a regression where the output_config addition
        accidentally dropped one of the required kwargs.
        """
        rec = AnthropicRecommender(
            api_key="test-key",
            model="claude-opus-4-7",
            effort="xhigh",
            max_tokens=4096,
        )
        fake_sdk = MagicMock()
        fake_sdk.messages.create.return_value = _mock_anthropic_response()
        rec._sdk = fake_sdk

        rec.call(system="system prompt text", user="user prompt text")

        _args, kwargs = fake_sdk.messages.create.call_args
        assert kwargs["model"] == "claude-opus-4-7"
        assert kwargs["max_tokens"] == 4096
        assert kwargs["system"] == "system prompt text"
        assert kwargs["messages"] == [
            {"role": "user", "content": "user prompt text"}
        ]


class TestConstructor:
    def test_missing_api_key_raises(self):
        """No CONCIERGE_ANTHROPIC_API_KEY and no ANTHROPIC_API_KEY
        env var → AnthropicClientError at construction. Unchanged
        behavior from pre-Opus-4.7 client; verified here so the
        switch to `effort` didn't silently regress the api-key
        resolution path.
        """
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(AnthropicClientError, match="API key"):
                AnthropicRecommender(
                    api_key=None,
                    model="claude-opus-4-7",
                    effort="xhigh",
                    max_tokens=4096,
                )

    def test_effort_attribute_set(self):
        rec = AnthropicRecommender(
            api_key="test-key",
            model="claude-opus-4-7",
            effort="xhigh",
            max_tokens=4096,
        )
        assert rec.effort == "xhigh"
        assert rec.model == "claude-opus-4-7"
        assert rec.max_tokens == 4096
