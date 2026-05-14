"""Sync HTTP client wrapping httpx for the concierge CLI.

The CLI is a single-shot tool; sync httpx is sufficient. This module
owns the error taxonomy: every httpx-level failure is mapped onto a
`ConciergeCliError` subclass with the exit code documented in
master-plan-v1.1.md §III. Callers receive validated pydantic models
or a typed exception — never a raw httpx Response.

Retry policy:
- Connect failure (ConnectError / ConnectTimeout): one retry after
  250ms. Covers uvicorn restart latency on a localhost shim.
- ReadTimeout: no retry. Server-side work was in flight; retrying
  could double-bill an Anthropic call inside /recommend.
- 5xx: no retry. Surface the error; let the operator decide.
"""
from __future__ import annotations

import os
import time
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from concierge_cli.errors import (
    MalformedResponseError,
    ServiceError,
    ServiceTimeoutError,
    ServiceUnreachableError,
)


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SECONDS = 90.0
CONNECT_RETRY_BACKOFF_SECONDS = 0.25

ResponseT = TypeVar("ResponseT", bound=BaseModel)


class HttpClient:
    """Sync HTTP shim over httpx with the CLI's error taxonomy.

    Honors $CONCIERGE_URL when set; otherwise binds to 127.0.0.1:8000.
    Context-manager use is supported; `close()` releases the underlying
    httpx.Client.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.base_url = base_url or os.environ.get("CONCIERGE_URL", DEFAULT_BASE_URL)
        self.timeout = timeout
        self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout)

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def post(
        self,
        path: str,
        json_body: dict[str, Any],
        *,
        response_model: type[ResponseT],
    ) -> ResponseT:
        """POST `json_body` to `path`; return the validated response model.

        Raises:
            ServiceUnreachableError: TCP connect failed twice (exit 3).
            ServiceTimeoutError: read timed out (exit 4).
            ServiceError: non-2xx response (exit 5).
            MalformedResponseError: 2xx body not JSON or did not validate (exit 6).
        """
        response = self._post_with_retry(path, json_body)
        self._raise_for_status(response)
        return self._parse_response(response, response_model)

    def _post_with_retry(self, path: str, json_body: dict[str, Any]) -> httpx.Response:
        try:
            return self._client.post(path, json=json_body)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            time.sleep(CONNECT_RETRY_BACKOFF_SECONDS)
            try:
                return self._client.post(path, json=json_body)
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                raise ServiceUnreachableError(self.base_url) from exc
        except httpx.ReadTimeout as exc:
            raise ServiceTimeoutError(self.timeout) from exc

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if 200 <= response.status_code < 300:
            return
        try:
            body = response.json()
            detail = body.get("detail") if isinstance(body, dict) else body
        except ValueError:
            detail = response.text or None
        raise ServiceError(status=response.status_code, detail=detail)

    @staticmethod
    def _parse_response(
        response: httpx.Response, response_model: type[ResponseT]
    ) -> ResponseT:
        try:
            raw_body = response.json()
        except ValueError as exc:
            raise MalformedResponseError.capture(response.text) from exc
        try:
            return response_model.model_validate(raw_body)
        except ValidationError as exc:
            raise MalformedResponseError.capture(raw_body) from exc
