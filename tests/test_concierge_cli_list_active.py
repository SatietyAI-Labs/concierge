"""Tests for `concierge list-active` subcommand — Stage 1A item 1b.

Covers:

- argparse surface: subcommand registered, flags advertised.
- Query-param plumbing: default `is_active=true`, `--dormant` flip,
  `--category` / `--pack-slug` pass-through.
- Render: group-by-pack shape, extended items-4+7 metadata columns,
  empty-result message, `--json` bypass.
- HTTP error-class plumbing through the new `HttpClient.get`: connect
  / timeout / 5xx / malformed map to exits 3 / 4 / 5 / 6, matching the
  `post` taxonomy (item-1b Decision D7).

Mocking strategy mirrors test_concierge_cli.py (item 1a):
- Subcommand behavior: mock HttpClient at the import boundary.
- Low-level HTTP behavior: monkeypatch httpx.Client.get so the real
  HttpClient exercises its exception-mapping code.
"""
from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock

import httpx
import pytest

from concierge_cli.client import HttpClient
from concierge_cli.main import main
from core.api.schemas import ToolList, ToolOut


def _tool(slug: str, **overrides) -> ToolOut:
    base = dict(
        id=1,
        slug=slug,
        name=slug,
        description=None,
        tool_type=None,
        category=None,
        install_method=None,
        is_in_manifest=True,
        is_active=True,
        lifecycle_state="installed",
        path=None,
        ambient_loading=None,
        agent_owner=None,
        best_for=None,
        limitation=None,
        prefix=None,
        transport=None,
        auth=None,
        succeeded_by=None,
        pack_id=None,
        pack_slug=None,
        pack_name=None,
        created_at=datetime(2026, 5, 15, 12, 0),
        updated_at=datetime(2026, 5, 15, 12, 0),
    )
    base.update(overrides)
    return ToolOut(**base)


def _tool_list(*tools: ToolOut) -> ToolList:
    return ToolList(items=list(tools), total=len(tools))


def _make_httpx_response(status_code: int, body: dict | list) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json"},
    )


@pytest.fixture
def mock_http_client(monkeypatch):
    instance = MagicMock(spec=HttpClient)
    instance.__enter__ = MagicMock(return_value=instance)
    instance.__exit__ = MagicMock(return_value=None)
    factory = MagicMock(return_value=instance)
    monkeypatch.setattr("concierge_cli.commands.list_active.HttpClient", factory)
    return instance


# ---- argparse surface ------------------------------------------------------


def test_subcommand_registered(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "list-active" in capsys.readouterr().out


def test_list_active_help_lists_flags(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["list-active", "--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for flag in ("--dormant", "--category", "--pack-slug", "--json"):
        assert flag in out


# ---- query-param plumbing + render -----------------------------------------


def test_happy_path_default_filter_and_grouped_render(mock_http_client, capsys):
    """Default invocation: filters to is_active=true, requests the full
    set, and renders tools grouped by pack with unpacked tools last.
    """
    mock_http_client.get.return_value = _tool_list(
        _tool("memory-store", pack_slug="memory-mcp", pack_name="Memory MCP"),
        _tool("ripgrep", category="search"),
    )
    exit_code = main(["list-active"])
    assert exit_code == 0

    call = mock_http_client.get.call_args
    assert call.args[0] == "/tools"
    params = call.kwargs["params"]
    assert params["is_active"] == "true"
    assert "dormant" not in params
    assert params["limit"] == 1000

    out = capsys.readouterr().out
    assert "2 active tool(s)" in out
    assert "[Memory MCP] (memory-mcp)" in out
    assert "memory-store" in out
    assert "[unpacked]" in out
    assert "ripgrep" in out


def test_dormant_flag_flips_filter(mock_http_client):
    mock_http_client.get.return_value = _tool_list()
    main(["list-active", "--dormant"])
    params = mock_http_client.get.call_args.kwargs["params"]
    assert params["dormant"] == "true"
    assert "is_active" not in params


def test_category_flag_plumbs_param(mock_http_client):
    mock_http_client.get.return_value = _tool_list()
    main(["list-active", "--category", "data-processing"])
    params = mock_http_client.get.call_args.kwargs["params"]
    assert params["category"] == "data-processing"


def test_pack_slug_flag_plumbs_param(mock_http_client):
    mock_http_client.get.return_value = _tool_list()
    main(["list-active", "--pack-slug", "memory-mcp"])
    params = mock_http_client.get.call_args.kwargs["params"]
    assert params["pack_slug"] == "memory-mcp"


def test_extended_metadata_columns_render(mock_http_client, capsys):
    """The items-4+7 catalog metadata columns surface inline — D3
    extended ToolOut so `list-active` can show use-case / anti-pattern
    prose without cross-referencing TOOL-MANIFEST.md.
    """
    mock_http_client.get.return_value = _tool_list(
        _tool(
            "ripgrep",
            agent_owner="alfred",
            best_for="fast code search",
            limitation="not for binary files",
            transport="cli",
        ),
    )
    main(["list-active"])
    out = capsys.readouterr().out
    assert "owner:" in out and "alfred" in out
    assert "best for:" in out and "fast code search" in out
    assert "limitation:" in out and "not for binary files" in out
    assert "cli" in out  # transport badge


def test_empty_result_renders_message(mock_http_client, capsys):
    mock_http_client.get.return_value = _tool_list()
    exit_code = main(["list-active"])
    assert exit_code == 0
    assert "No active tools match" in capsys.readouterr().out


def test_empty_dormant_result_uses_dormant_noun(mock_http_client, capsys):
    mock_http_client.get.return_value = _tool_list()
    main(["list-active", "--dormant"])
    assert "No dormant tools match" in capsys.readouterr().out


def test_json_mode_bypasses_render(mock_http_client, capsys):
    mock_http_client.get.return_value = _tool_list(_tool("ripgrep"))
    exit_code = main(["list-active", "--json"])
    assert exit_code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["total"] == 1
    assert parsed["items"][0]["slug"] == "ripgrep"


# ---- HTTP error-class plumbing through HttpClient.get ----------------------


def test_service_unreachable_exits_3(monkeypatch, capsys):
    def always_refused(self, *args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("httpx.Client.get", always_refused)
    exit_code = main(["list-active"])
    assert exit_code == 3
    assert "cannot reach service" in capsys.readouterr().err


def test_timeout_exits_4(monkeypatch, capsys):
    def always_timeout(self, *args, **kwargs):
        raise httpx.ReadTimeout("read too slow")

    monkeypatch.setattr("httpx.Client.get", always_timeout)
    exit_code = main(["list-active", "--timeout", "5"])
    assert exit_code == 4
    assert "timed out" in capsys.readouterr().err


def test_http_500_exits_5(monkeypatch, capsys):
    def fake_get(self, *args, **kwargs):
        return _make_httpx_response(500, {"detail": "internal server error"})

    monkeypatch.setattr("httpx.Client.get", fake_get)
    exit_code = main(["list-active"])
    captured = capsys.readouterr()
    assert exit_code == 5
    assert "500" in captured.err


def test_malformed_response_exits_6(monkeypatch, capsys):
    def fake_get(self, *args, **kwargs):
        return _make_httpx_response(200, {"unexpected": "shape"})

    monkeypatch.setattr("httpx.Client.get", fake_get)
    exit_code = main(["list-active"])
    assert exit_code == 6
    assert "unexpected response shape" in capsys.readouterr().err
