"""Stage 1A item 1a — end-to-end tests for `concierge recommend`.

Mocking strategy:
- High-level subcommand behavior (happy / json / render variants):
  mock `HttpClient` at the `concierge_cli.commands.recommend.HttpClient`
  import boundary.
- Low-level client behavior (retry, timeout, status-code mapping,
  malformed body, the outer catch-all): mock `httpx.Client.post`
  via `monkeypatch.setattr` so the real `HttpClient` exercises its
  exception-mapping code.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from concierge_cli.client import DEFAULT_BASE_URL, DEFAULT_TIMEOUT_SECONDS, HttpClient
from concierge_cli.main import main
from core.recommend.schemas import (
    LatencyBreakdown,
    RecommendResponse,
    TokenUsage,
    ToolRecommendation,
)


def _valid_response(
    *,
    memory_available: bool = True,
    side_observations: list[str] | None = None,
) -> RecommendResponse:
    return RecommendResponse(
        request_id="00000000-0000-0000-0000-000000000000",
        recommendations=[
            ToolRecommendation(
                rank=1,
                tool_slug="csvkit",
                tool_name="csvkit",
                rationale="Fast CSV operations with column awareness.",
                confidence="high",
                is_in_catalog=True,
                category="data-processing",
                install_method="pipx",
                risk_cost="~5MB, no deps",
            ),
        ],
        memory_available=memory_available,
        memory_hit_count=2,
        model="claude-opus-4-7",
        effort="xhigh",
        latency_ms=LatencyBreakdown(total=4200, memory=300, model=3600, parse=200),
        token_usage=TokenUsage(input=1245, output=312, total=1557),
        stop_reason="end_turn",
        side_observations=side_observations,
    )


def _make_httpx_response(status_code: int, body: dict | list) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json"},
    )


@pytest.fixture
def mock_http_client(monkeypatch):
    """Replace `concierge_cli.commands.recommend.HttpClient` with a
    MagicMock instance configured to behave as a context manager.
    """
    instance = MagicMock(spec=HttpClient)
    instance.__enter__ = MagicMock(return_value=instance)
    instance.__exit__ = MagicMock(return_value=None)

    factory = MagicMock(return_value=instance)
    monkeypatch.setattr("concierge_cli.commands.recommend.HttpClient", factory)
    return instance


# ---- High-level subcommand behavior ----------------------------------------


def test_recommend_happy_path(mock_http_client, capsys):
    mock_http_client.post.return_value = _valid_response()

    exit_code = main(["recommend", "find a tool to count CSV lines"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "1. csvkit" in captured.out
    assert "high" in captured.out
    assert "in catalog" in captured.out
    assert "stop_reason: end_turn" in captured.out


def test_recommend_json_mode(mock_http_client, capsys):
    response = _valid_response()
    mock_http_client.post.return_value = response

    exit_code = main(["recommend", "test task", "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    parsed = json.loads(captured.out)
    assert parsed["request_id"] == response.request_id
    assert parsed["model"] == "claude-opus-4-7"


def test_recommend_renders_memory_unavailable_warning(mock_http_client, capsys):
    mock_http_client.post.return_value = _valid_response(memory_available=False)

    exit_code = main(["recommend", "test task"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "WARNING: MEMORY UNAVAILABLE" in captured.out
    assert ("=" * 80) in captured.out
    assert "weaker" in captured.out.lower()


def test_recommend_renders_side_observations_section(mock_http_client, capsys):
    mock_http_client.post.return_value = _valid_response(
        side_observations=["Firefox DevTools loaded but unused this session."]
    )

    exit_code = main(["recommend", "test"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Observations:" in captured.out
    assert "Firefox DevTools loaded" in captured.out


# ---- Low-level HttpClient behavior (real client + mocked httpx) ------------


def test_service_unreachable_exits_3(monkeypatch, capsys):
    def always_refused(self, *args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("httpx.Client.post", always_refused)

    exit_code = main(["recommend", "test task"])
    captured = capsys.readouterr()

    assert exit_code == 3
    assert "cannot reach service" in captured.err
    assert "concierge.service" in captured.err


def test_service_unreachable_retry_recovers(monkeypatch):
    call_count = {"n": 0}

    def flaky(self, *args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise httpx.ConnectError("first try fails")
        return _make_httpx_response(200, _valid_response().model_dump(mode="json"))

    monkeypatch.setattr("httpx.Client.post", flaky)

    exit_code = main(["recommend", "test task"])

    assert exit_code == 0
    assert call_count["n"] == 2


def test_timeout_exits_4(monkeypatch, capsys):
    def always_timeout(self, *args, **kwargs):
        raise httpx.ReadTimeout("read too slow")

    monkeypatch.setattr("httpx.Client.post", always_timeout)

    exit_code = main(["recommend", "--timeout", "5", "test task"])
    captured = capsys.readouterr()

    assert exit_code == 4
    assert "timed out" in captured.err
    assert "5s" in captured.err


def test_http_502_structured_detail_exits_5(monkeypatch, capsys):
    def fake_post(self, *args, **kwargs):
        return _make_httpx_response(
            502,
            {
                "detail": {
                    "error": "recommendation_parse_failed",
                    "message": "bad parse",
                }
            },
        )

    monkeypatch.setattr("httpx.Client.post", fake_post)

    exit_code = main(["recommend", "test task"])
    captured = capsys.readouterr()

    assert exit_code == 5
    assert "502" in captured.err
    assert "recommendation_parse_failed" in captured.err
    assert "bad parse" in captured.err


def test_http_500_string_detail_exits_5(monkeypatch, capsys):
    def fake_post(self, *args, **kwargs):
        return _make_httpx_response(500, {"detail": "internal server error"})

    monkeypatch.setattr("httpx.Client.post", fake_post)

    exit_code = main(["recommend", "test task"])
    captured = capsys.readouterr()

    assert exit_code == 5
    assert "500" in captured.err
    assert "internal server error" in captured.err


def test_http_422_exits_5(monkeypatch, capsys):
    def fake_post(self, *args, **kwargs):
        return _make_httpx_response(
            422,
            {
                "detail": [
                    {
                        "loc": ["body", "task"],
                        "msg": "field required",
                        "type": "value_error.missing",
                    }
                ]
            },
        )

    monkeypatch.setattr("httpx.Client.post", fake_post)

    exit_code = main(["recommend", "test task"])
    captured = capsys.readouterr()

    assert exit_code == 5
    assert "422" in captured.err


def test_malformed_response_exits_6(monkeypatch, capsys):
    def fake_post(self, *args, **kwargs):
        return _make_httpx_response(200, {"unexpected": "shape"})

    monkeypatch.setattr("httpx.Client.post", fake_post)

    exit_code = main(["recommend", "test task"])
    captured = capsys.readouterr()

    assert exit_code == 6
    assert "unexpected response shape" in captured.err
    m = re.search(r"raw body at (\S+)", captured.err)
    assert m is not None, "tmpfile path missing from stderr"
    tmpfile = Path(m.group(1))
    assert tmpfile.exists()
    assert "unexpected" in tmpfile.read_text(encoding="utf-8")


# ---- argparse / top-level flags --------------------------------------------


def test_missing_task_arg_exits_2(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["recommend"])

    assert exc.value.code == 2


def test_timeout_flag_honored(monkeypatch):
    captured = {}
    original_init = HttpClient.__init__

    def init_spy(self, base_url=None, timeout=DEFAULT_TIMEOUT_SECONDS):
        captured["timeout"] = timeout
        original_init(self, base_url=base_url, timeout=timeout)

    monkeypatch.setattr(HttpClient, "__init__", init_spy)

    def fake_post(self, *args, **kwargs):
        return _make_httpx_response(200, _valid_response().model_dump(mode="json"))

    monkeypatch.setattr("httpx.Client.post", fake_post)

    main(["recommend", "--timeout", "30", "test task"])

    assert captured["timeout"] == 30.0


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])

    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "concierge" in captured.out


def test_concierge_url_env_var(monkeypatch):
    monkeypatch.setenv("CONCIERGE_URL", "http://example.invalid:9999")
    client = HttpClient()
    try:
        assert client.base_url == "http://example.invalid:9999"
    finally:
        client.close()

    monkeypatch.delenv("CONCIERGE_URL")
    client = HttpClient()
    try:
        assert client.base_url == DEFAULT_BASE_URL
    finally:
        client.close()


def test_httpx_transport_error_outer_catchall_exits_3(monkeypatch, capsys):
    """Anything httpx-level that slips past client.py's specific catches
    must land in main.py's `httpx.TransportError` catch-all and route
    to exit 3 with the service-unreachable user message.

    PoolTimeout is a httpx.TransportError subclass that client.py does
    NOT catch specifically — perfect simulation of an unhandled
    transport-level failure.
    """

    def raise_pool_timeout(self, *args, **kwargs):
        raise httpx.PoolTimeout("pool exhausted")

    monkeypatch.setattr("httpx.Client.post", raise_pool_timeout)

    exit_code = main(["recommend", "test task"])
    captured = capsys.readouterr()

    assert exit_code == 3
    assert "cannot reach service" in captured.err
