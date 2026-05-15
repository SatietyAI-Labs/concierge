"""Tests for `concierge request-tool` subcommand — Stage 1A item 5.

Covers:

- argparse surface shape: every flag accepted, help-text framing
  category-neutral (no "MCP server" leakage).
- Worker-form auto-infer: --agent-id <worker> with no
  --escalation-target lands escalation_target=alfred in the body.
- Worker-form client-side validation: --gap + --workaround required
  when worker form detected.
- --agent-id rejection: unknown codename → exit 2 with clear error.
- HTTP error-class plumbing: 422 / 5xx / connect / timeout / malformed
  (exits 3 / 4 / 5 / 6 per item 1a precedent).
- Category-agnostic end-to-end skill-request fixture per operator
  watch item (--category skill round-trips through CLI surface).
- Help text framing: category-agnostic vocabulary verified.

Mocking strategy mirrors test_concierge_cli.py (item 1a):
- Subcommand behavior: mock HttpClient at the import boundary.
- Lower-level HTTP behavior: monkeypatch httpx.Client.post for real
  HttpClient exception-mapping coverage.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from unittest.mock import MagicMock

import httpx
import pytest

from concierge_cli.client import HttpClient
from concierge_cli.main import main
from core.lifecycle_store.schema import RequestDetail


def _valid_request_detail(**overrides) -> RequestDetail:
    base = dict(
        id=42,
        filename="2026-05-14-2100-worker-scout-csvkit.md",
        folder="pending",
        status="pending",
        tool_name="csvkit",
        tool_slug="csvkit",
        category="cli",
        confidence="high",
        is_discovered=False,
        escalation_target="alfred",
        is_parseable=True,
        parse_error=None,
        created_at=datetime(2026, 5, 14, 21, 0),
        updated_at=datetime(2026, 5, 14, 21, 0),
        raw_markdown="status: pending\n\n# Tool Request: csvkit\n",
    )
    base.update(overrides)
    return RequestDetail(**base)


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
    monkeypatch.setattr("concierge_cli.commands.request_tool.HttpClient", factory)
    return instance


# ---- argparse surface ------------------------------------------------------


class TestArgparseSurface:
    def test_subcommand_registered(self, capsys):
        """`concierge --help` advertises `request-tool` subcommand."""
        with pytest.raises(SystemExit) as exc:
            main(["--help"])
        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "request-tool" in captured.out

    def test_request_tool_help_lists_flags(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["request-tool", "--help"])
        assert exc.value.code == 0
        captured = capsys.readouterr()
        # Worker-form + Alfred-form flags advertised.
        for flag in (
            "--tool-name",
            "--category",
            "--agent-id",
            "--escalation-target",
            "--gap",
            "--workaround",
            "--task-context",
            "--confidence",
        ):
            assert flag in captured.out

    def test_missing_tool_name_exits_2(self):
        """argparse's `required=True` on --tool-name fires before
        run() ever sees the args.
        """
        with pytest.raises(SystemExit) as exc:
            main(["request-tool"])
        assert exc.value.code == 2

    def test_help_text_is_category_agnostic(self, capsys):
        """Operator scope clarification: help text must not say
        'MCP server'. The accepted vocabulary covers all four catalog
        categories.
        """
        with pytest.raises(SystemExit) as exc:
            main(["request-tool", "--help"])
        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "MCP server" not in captured.out
        # Acceptable framing — at least one of these phrases should
        # appear so the category-neutrality is visible to readers.
        text = captured.out.lower()
        assert any(
            word in text
            for word in ("skill", "package", "capability")
        ), (
            "help text should explicitly name multiple categories to "
            "signal category-agnosticism; got:\n" + captured.out
        )


# ---- Body shaping (Alfred form) --------------------------------------------


class TestAlfredFormBodyShape:
    def test_minimal_alfred_form(self, mock_http_client):
        mock_http_client.post.return_value = _valid_request_detail(
            escalation_target=None,
        )
        exit_code = main(["request-tool", "--tool-name", "csvkit"])
        assert exit_code == 0
        call = mock_http_client.post.call_args
        assert call.args[0] == "/requests"
        body = call.args[1]
        assert body == {"tool_name": "csvkit"}

    def test_full_alfred_form_body_shape(self, mock_http_client):
        mock_http_client.post.return_value = _valid_request_detail(
            escalation_target=None
        )
        exit_code = main([
            "request-tool",
            "--tool-name", "csvkit",
            "--category", "cli",
            "--install-method", "pipx",
            "--task-context", "profiling a CSV",
            "--why-this-tool", "lightweight",
            "--alternatives", "pandas inline",
            "--risk-cost", "small disk",
            "--confidence", "high",
            "--discovered",
            "--source", "npm registry",
            "--evidence", "10k stars",
        ])
        assert exit_code == 0
        body = mock_http_client.post.call_args.args[1]
        assert body == {
            "tool_name": "csvkit",
            "category": "cli",
            "install_method": "pipx",
            "task_context": "profiling a CSV",
            "why_this_tool": "lightweight",
            "alternatives_considered": "pandas inline",
            "risk_cost": "small disk",
            "confidence": "high",
            "is_discovered": True,
            "source": "npm registry",
            "evidence": "10k stars",
        }

    def test_no_agent_id_no_escalation_target(self, mock_http_client):
        """Alfred-form: no --agent-id → no escalation_target in body."""
        mock_http_client.post.return_value = _valid_request_detail(
            escalation_target=None
        )
        main(["request-tool", "--tool-name", "csvkit"])
        body = mock_http_client.post.call_args.args[1]
        assert "agent_id" not in body
        assert "escalation_target" not in body


# ---- Worker form auto-infer + validation ----------------------------------


class TestWorkerFormAutoInfer:
    def test_worker_agent_id_auto_infers_alfred(self, mock_http_client):
        mock_http_client.post.return_value = _valid_request_detail()
        exit_code = main([
            "request-tool",
            "--tool-name", "csvkit",
            "--agent-id", "scout",
            "--gap", "no CLI for column stats",
            "--workaround", "pandas in REPL",
        ])
        assert exit_code == 0
        body = mock_http_client.post.call_args.args[1]
        assert body["agent_id"] == "scout"
        assert body["escalation_target"] == "alfred"
        assert body["gap"] == "no CLI for column stats"
        assert body["workaround_used"] == "pandas in REPL"

    def test_explicit_escalation_target_overrides_inferred(
        self, mock_http_client
    ):
        """Operator can pass --escalation-target operator explicitly
        even when --agent-id names a worker. The auto-infer is a
        convenience, not a forcing function.
        """
        mock_http_client.post.return_value = _valid_request_detail(
            escalation_target="operator"
        )
        exit_code = main([
            "request-tool",
            "--tool-name", "csvkit",
            "--agent-id", "scout",
            "--escalation-target", "operator",
            "--gap", "x",
            "--workaround", "y",
        ])
        assert exit_code == 0
        body = mock_http_client.post.call_args.args[1]
        assert body["escalation_target"] == "operator"

    def test_alfred_as_agent_id_no_auto_infer(self, mock_http_client):
        """Alfred-as-filer doesn't auto-infer to anything. Alfred's
        own onward escalations pass --escalation-target explicitly.
        """
        mock_http_client.post.return_value = _valid_request_detail(
            escalation_target=None
        )
        main([
            "request-tool",
            "--tool-name", "csvkit",
            "--agent-id", "alfred",
        ])
        body = mock_http_client.post.call_args.args[1]
        assert body["agent_id"] == "alfred"
        assert "escalation_target" not in body

    def test_agent_id_case_normalized_to_lowercase(self, mock_http_client):
        """`--agent-id Scout` lowercases on the wire so server-side
        + downstream filename prefix use the canonical form.
        """
        mock_http_client.post.return_value = _valid_request_detail()
        main([
            "request-tool",
            "--tool-name", "csvkit",
            "--agent-id", "Scout",
            "--gap", "x",
            "--workaround", "y",
        ])
        body = mock_http_client.post.call_args.args[1]
        assert body["agent_id"] == "scout"


class TestWorkerFormValidation:
    def test_worker_missing_gap_exits_2(self, mock_http_client, capsys):
        exit_code = main([
            "request-tool",
            "--tool-name", "csvkit",
            "--agent-id", "scout",
            "--workaround", "pandas in REPL",
        ])
        assert exit_code == 2
        captured = capsys.readouterr()
        assert "--gap" in captured.err
        # POST never fired.
        assert mock_http_client.post.call_count == 0

    def test_worker_missing_workaround_exits_2(self, mock_http_client, capsys):
        exit_code = main([
            "request-tool",
            "--tool-name", "csvkit",
            "--agent-id", "scout",
            "--gap", "no CLI for column stats",
        ])
        assert exit_code == 2
        captured = capsys.readouterr()
        assert "--workaround" in captured.err
        assert mock_http_client.post.call_count == 0

    def test_worker_missing_both_lists_both(self, mock_http_client, capsys):
        exit_code = main([
            "request-tool",
            "--tool-name", "csvkit",
            "--agent-id", "scout",
        ])
        assert exit_code == 2
        captured = capsys.readouterr()
        # Single error names both missing fields.
        assert "--gap" in captured.err
        assert "--workaround" in captured.err

    def test_unknown_agent_id_exits_2(self, mock_http_client, capsys):
        exit_code = main([
            "request-tool",
            "--tool-name", "csvkit",
            "--agent-id", "unknown-codename",
        ])
        assert exit_code == 2
        captured = capsys.readouterr()
        assert "not a recognized codename" in captured.err
        assert mock_http_client.post.call_count == 0

    def test_gap_without_agent_id_treated_as_worker_form_and_fails(
        self, mock_http_client, capsys
    ):
        """The is_worker_form predicate catches "operator passed --gap
        but forgot --agent-id" as worker form. CLI surfaces a clear
        error rather than silently treating it as Alfred-form.
        """
        exit_code = main([
            "request-tool",
            "--tool-name", "csvkit",
            "--gap", "no CLI for column stats",
        ])
        assert exit_code == 2
        captured = capsys.readouterr()
        # Error mentions agent_id requirement for worker form.
        assert "agent-id" in captured.err.lower() or "agent_id" in captured.err.lower()


# ---- Render output ---------------------------------------------------------


class TestRenderOutput:
    def test_worker_form_response_shows_routing(self, mock_http_client, capsys):
        mock_http_client.post.return_value = _valid_request_detail()
        main([
            "request-tool",
            "--tool-name", "csvkit",
            "--agent-id", "scout",
            "--gap", "x",
            "--workaround", "y",
        ])
        captured = capsys.readouterr()
        assert "Filed: csvkit" in captured.out
        assert "routes to: alfred" in captured.out

    def test_alfred_form_response_omits_routing(self, mock_http_client, capsys):
        mock_http_client.post.return_value = _valid_request_detail(
            escalation_target=None
        )
        main(["request-tool", "--tool-name", "csvkit"])
        captured = capsys.readouterr()
        assert "Filed: csvkit" in captured.out
        assert "routes to" not in captured.out

    def test_json_mode_bypasses_render(self, mock_http_client, capsys):
        mock_http_client.post.return_value = _valid_request_detail()
        exit_code = main([
            "request-tool",
            "--tool-name", "csvkit",
            "--agent-id", "scout",
            "--gap", "x",
            "--workaround", "y",
            "--json",
        ])
        assert exit_code == 0
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["tool_name"] == "csvkit"
        assert parsed["escalation_target"] == "alfred"


# ---- HTTP error-class plumbing (mirrors item 1a precedent) -----------------


class TestHttpErrorClasses:
    def test_connect_refused_exits_3(self, monkeypatch, capsys):
        def always_refused(self, *args, **kwargs):
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr("httpx.Client.post", always_refused)

        exit_code = main(["request-tool", "--tool-name", "csvkit"])
        captured = capsys.readouterr()
        assert exit_code == 3
        assert "cannot reach service" in captured.err

    def test_timeout_exits_4(self, monkeypatch, capsys):
        def always_timeout(self, *args, **kwargs):
            raise httpx.ReadTimeout("slow")

        monkeypatch.setattr("httpx.Client.post", always_timeout)

        exit_code = main([
            "request-tool", "--timeout", "5", "--tool-name", "csvkit",
        ])
        captured = capsys.readouterr()
        assert exit_code == 4
        assert "timed out" in captured.err

    def test_409_collision_exits_5(self, monkeypatch, capsys):
        def fake_post(self, *args, **kwargs):
            return _make_httpx_response(
                409,
                {
                    "detail": {
                        "error": "request_filename_collision",
                        "message": "already exists",
                    }
                },
            )

        monkeypatch.setattr("httpx.Client.post", fake_post)

        exit_code = main(["request-tool", "--tool-name", "csvkit"])
        captured = capsys.readouterr()
        assert exit_code == 5
        assert "409" in captured.err

    def test_malformed_response_exits_6(self, monkeypatch, capsys):
        def fake_post(self, *args, **kwargs):
            return _make_httpx_response(200, {"unexpected": "shape"})

        monkeypatch.setattr("httpx.Client.post", fake_post)

        exit_code = main(["request-tool", "--tool-name", "csvkit"])
        captured = capsys.readouterr()
        assert exit_code == 6
        assert "unexpected response shape" in captured.err


# ---- Category-agnostic skill-request fixture (operator watch item) ---------


class TestCategoryAgnosticSkillRequest:
    """End-to-end test for the operator-mandated category-agnosticism
    invariant: a skill request from a worker must round-trip cleanly
    through the CLI surface with no "MCP server" assumption leakage.
    Help text framing already pinned by `test_help_text_is_category_agnostic`;
    this fixture covers the actual filing flow.
    """

    def test_skill_worker_request_round_trips(self, mock_http_client, capsys):
        mock_http_client.post.return_value = _valid_request_detail(
            tool_name="claude-code-review-skill",
            category="skill",
            filename="2026-05-14-2100-worker-scout-claude-code-review-skill.md",
        )
        exit_code = main([
            "request-tool",
            "--tool-name", "claude-code-review-skill",
            "--category", "skill",
            "--agent-id", "scout",
            "--task-context", "reviewing a PR for compliance with brand voice",
            "--gap", "no installed skill captures our brand-voice review patterns",
            "--workaround", "did the review manually from memory",
            "--confidence", "high",
        ])
        assert exit_code == 0
        body = mock_http_client.post.call_args.args[1]
        assert body == {
            "tool_name": "claude-code-review-skill",
            "category": "skill",
            "task_context": "reviewing a PR for compliance with brand voice",
            "confidence": "high",
            "agent_id": "scout",
            "escalation_target": "alfred",
            "gap": "no installed skill captures our brand-voice review patterns",
            "workaround_used": "did the review manually from memory",
        }
        captured = capsys.readouterr()
        assert "Filed: claude-code-review-skill" in captured.out
        assert "category: skill" in captured.out
        assert "routes to: alfred" in captured.out
        # No "MCP" leakage in the rendered confirmation.
        assert "MCP" not in captured.out
