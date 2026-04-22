"""Thin Anthropic client wrapper for POST /recommend.

Responsibilities:

- Resolve the API key from `CONCIERGE_ANTHROPIC_API_KEY` first,
  then fall back to `ANTHROPIC_API_KEY` (Anthropic SDK default).
- Pin the model + temperature + max_tokens from settings; log a
  loud DEBUG line at construction AND per-request whenever a
  non-zero temperature override is active.
- Call the Messages API with the composed (system, user) prompt.
- Extract `{content, stop_reason, tokens_in, tokens_out}` into a
  plain dict so the service layer doesn't depend on the Anthropic
  SDK types.

Retries: none. A transient Anthropic error surfaces as
`AnthropicError` which the service layer allows to propagate as
HTTP 502. Retries are a potential Day 4-5 enhancement if the 48h
shakedown surfaces flaky-call patterns; premature retry logic
complicates the log-based debugging surface.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Optional


logger = logging.getLogger(__name__)


class AnthropicClientError(RuntimeError):
    """Raised when the Anthropic SDK returns an error or an
    unexpected response shape. Distinct from
    `RecommendationParseError` (which operates on the content
    string) and `MemoryUnavailableError` (memory subsystem).
    """


@dataclass(frozen=True)
class AnthropicCall:
    """Flattened result of one Anthropic Messages API call."""

    content: str
    stop_reason: Optional[str]
    tokens_in: int
    tokens_out: int
    model_echo: str
    latency_ms: int


def _resolve_api_key(settings_key: Optional[str]) -> Optional[str]:
    """Check Concierge-prefixed env first, then SDK-default env.

    Returns the raw API key string or None. Logging is deferred
    to the caller so the client constructor can emit a single
    ERROR log if both resolutions miss.
    """
    if settings_key:
        return settings_key
    # Anthropic SDK falls back to this env var by default, but we
    # read it explicitly so a missing key is observable at the
    # Concierge boundary rather than inside the SDK.
    env_key = os.environ.get("ANTHROPIC_API_KEY")
    return env_key


class AnthropicRecommender:
    """Thin wrapper around the Anthropic Messages API.

    Holds a cached SDK client; safe to reuse across requests.
    """

    def __init__(
        self,
        *,
        api_key: Optional[str],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> None:
        resolved = _resolve_api_key(api_key)
        if not resolved:
            raise AnthropicClientError(
                "Anthropic API key not found in CONCIERGE_ANTHROPIC_API_KEY or "
                "ANTHROPIC_API_KEY env vars"
            )
        self._api_key = resolved
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._sdk = None  # lazy

        if temperature != 0.0:
            logger.debug(
                "recommend.temperature_override_active model=%s temperature=%s "
                "(non-zero temperature is dev/tuning only; soak must run at 0.0)",
                model,
                temperature,
            )
        logger.info(
            "AnthropicRecommender configured: model=%s temperature=%s max_tokens=%d",
            model,
            temperature,
            max_tokens,
        )

    def _get_sdk(self):
        if self._sdk is None:
            from anthropic import Anthropic

            self._sdk = Anthropic(api_key=self._api_key)
        return self._sdk

    def call(self, *, system: str, user: str) -> AnthropicCall:
        """Issue one Messages API call with the composed prompts.

        Per-call DEBUG logs the temperature-override state so a
        soak log reader can spot any non-zero-temperature calls
        immediately without reading service configuration.
        """
        if self.temperature != 0.0:
            logger.debug(
                "recommend.call temperature_override=%s model=%s",
                self.temperature,
                self.model,
            )

        sdk = self._get_sdk()
        start = time.monotonic()
        try:
            response = sdk.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:  # anthropic.APIError, network, etc.
            raise AnthropicClientError(f"Anthropic call failed: {exc}") from exc
        latency_ms = int((time.monotonic() - start) * 1000)

        try:
            content = _extract_text(response)
            stop_reason = getattr(response, "stop_reason", None)
            usage = getattr(response, "usage", None)
            tokens_in = int(getattr(usage, "input_tokens", 0) or 0) if usage else 0
            tokens_out = int(getattr(usage, "output_tokens", 0) or 0) if usage else 0
            # Cache tokens (when present) fold into `tokens_in` so
            # the aggregate cost matches billing without exposing
            # a per-response cache dimension we don't yet use.
            for attr in ("cache_creation_input_tokens", "cache_read_input_tokens"):
                if usage is not None:
                    extra = getattr(usage, attr, 0) or 0
                    tokens_in += int(extra)
            model_echo = getattr(response, "model", self.model)
        except Exception as exc:
            raise AnthropicClientError(
                f"Anthropic response shape unexpected: {exc}"
            ) from exc

        return AnthropicCall(
            content=content,
            stop_reason=stop_reason,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            model_echo=model_echo,
            latency_ms=latency_ms,
        )


def _extract_text(response) -> str:
    """Pull text content from the Messages API response.

    The SDK returns `response.content` as a list of content blocks;
    the first `TextBlock` carries the JSON we asked for. Any
    non-text block at the head is unexpected and raises.
    """
    blocks = getattr(response, "content", None)
    if not blocks:
        raise AnthropicClientError("response has no content blocks")
    head = blocks[0]
    text = getattr(head, "text", None)
    if text is None:
        raise AnthropicClientError(
            f"first content block is not text (type={type(head).__name__})"
        )
    return text
