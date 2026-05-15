"""Tests for `concierge enable` / `concierge disable` — Stage 1A item 1b.

Covers:

- argparse surface: both subcommands registered; the enable
  config-source mutually-exclusive-required group (D2 — passing both
  or neither exits 2 at the argparse layer).
- Direct in-process call (D1): enable / disable invoke
  `core.agent_config.openclaw_writer.set_mcp_server` — no HTTP.
- Config sourcing (D2): `--config-json` and `--config-file` both
  parse to the dict handed to the writer.
- Error contract: unknown agent, malformed JSON, missing file,
  non-object payload, and writer-raised FileNotFoundError all map to
  exit 2 (UsageError).
- End-to-end: an enable→disable round-trip against a real `tmp_path`
  openclaw.json driving the REAL `set_mcp_server` (no mock) — the test
  that actually exercises the D1 direct-call decision. The live
  AGENT_PATHS entry is patched to the tmp file (item-1b Decision D6 —
  no operator-facing --config-path; tests use the AGENT_PATHS seam).

Mocking strategy:
- Call-shape assertions: mock `set_mcp_server` at this command
  module's import boundary.
- End-to-end / idempotency: patch `AGENT_PATHS` so the real writer
  targets a tmp file.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from concierge_cli.main import main
from core.agent_config import openclaw_writer


@pytest.fixture
def mock_set_mcp_server(monkeypatch):
    """Replace `set_mcp_server` at the agent_config command module's
    import boundary so call shape can be asserted without filesystem
    I/O. End-to-end tests deliberately do NOT use this fixture.
    """
    mock = MagicMock(return_value=None)
    monkeypatch.setattr(
        "concierge_cli.commands.agent_config.set_mcp_server", mock
    )
    return mock


# ---- argparse surface ------------------------------------------------------


def test_enable_subcommand_registered(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "enable" in capsys.readouterr().out


def test_disable_subcommand_registered(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "disable" in capsys.readouterr().out


def test_enable_help_lists_config_flags(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["enable", "--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "--config-file" in out
    assert "--config-json" in out


def test_enable_missing_config_source_exits_2(capsys):
    """Neither --config-file nor --config-json: the required
    mutually-exclusive group fails at the argparse layer (exit 2).
    """
    with pytest.raises(SystemExit) as exc:
        main(["enable", "scout", "firefox"])
    assert exc.value.code == 2


def test_enable_both_config_sources_exits_2(capsys):
    """Both flags at once: mutually-exclusive group fails (exit 2).
    The error names both flags.
    """
    with pytest.raises(SystemExit) as exc:
        main([
            "enable", "scout", "firefox",
            "--config-file", "/tmp/x.json",
            "--config-json", "{}",
        ])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "--config-file" in err and "--config-json" in err


# ---- enable: direct call + config sourcing ---------------------------------


def test_enable_config_json_calls_writer_and_renders(mock_set_mcp_server, capsys):
    exit_code = main([
        "enable", "scout", "firefox",
        "--config-json", '{"command": "firefox-mcp", "args": ["--headless"]}',
    ])
    assert exit_code == 0
    mock_set_mcp_server.assert_called_once_with(
        "scout", "firefox", {"command": "firefox-mcp", "args": ["--headless"]}
    )
    out = capsys.readouterr().out
    assert "Enabled: firefox" in out
    assert "scout" in out


def test_enable_config_file_calls_writer(mock_set_mcp_server, tmp_path):
    cfg = tmp_path / "server.json"
    cfg.write_text('{"command": "memory-mcp"}', encoding="utf-8")
    exit_code = main([
        "enable", "alfred", "memory", "--config-file", str(cfg),
    ])
    assert exit_code == 0
    mock_set_mcp_server.assert_called_once_with(
        "alfred", "memory", {"command": "memory-mcp"}
    )


def test_enable_unknown_agent_exits_2(mock_set_mcp_server, capsys):
    exit_code = main([
        "enable", "nobody", "firefox", "--config-json", "{}",
    ])
    assert exit_code == 2
    assert "unknown agent codename" in capsys.readouterr().err
    assert mock_set_mcp_server.call_count == 0


def test_enable_bad_config_json_exits_2(mock_set_mcp_server, capsys):
    exit_code = main([
        "enable", "scout", "firefox", "--config-json", "{not json",
    ])
    assert exit_code == 2
    assert "not valid JSON" in capsys.readouterr().err
    assert mock_set_mcp_server.call_count == 0


def test_enable_config_file_not_found_exits_2(mock_set_mcp_server, capsys):
    exit_code = main([
        "enable", "scout", "firefox",
        "--config-file", "/nonexistent/server.json",
    ])
    assert exit_code == 2
    assert "--config-file not found" in capsys.readouterr().err
    assert mock_set_mcp_server.call_count == 0


def test_enable_non_object_config_exits_2(mock_set_mcp_server, capsys):
    """A JSON array is valid JSON but not a server-config object."""
    exit_code = main([
        "enable", "scout", "firefox", "--config-json", "[1, 2, 3]",
    ])
    assert exit_code == 2
    assert "must be a JSON object" in capsys.readouterr().err
    assert mock_set_mcp_server.call_count == 0


def test_enable_writer_file_not_found_exits_2(mock_set_mcp_server, capsys):
    """The writer raises FileNotFoundError when the agent's
    openclaw.json is absent on disk — mapped to exit 2 (UsageError).
    """
    mock_set_mcp_server.side_effect = FileNotFoundError(
        "openclaw.json not found at /home/x/.openclaw-content/openclaw.json"
    )
    exit_code = main([
        "enable", "scout", "firefox", "--config-json", "{}",
    ])
    assert exit_code == 2
    assert "openclaw.json not found" in capsys.readouterr().err


def test_enable_json_mode(mock_set_mcp_server, capsys):
    exit_code = main([
        "enable", "scout", "firefox", "--config-json", "{}", "--json",
    ])
    assert exit_code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed == {
        "action": "enable",
        "agent_id": "scout",
        "server_name": "firefox",
        "status": "ok",
    }


# ---- disable: direct call --------------------------------------------------


def test_disable_calls_writer_with_none_and_renders(mock_set_mcp_server, capsys):
    exit_code = main(["disable", "radar", "brave-search"])
    assert exit_code == 0
    mock_set_mcp_server.assert_called_once_with("radar", "brave-search", None)
    out = capsys.readouterr().out
    assert "Disabled: brave-search" in out
    assert "radar" in out


def test_disable_unknown_agent_exits_2(mock_set_mcp_server, capsys):
    exit_code = main(["disable", "nobody", "firefox"])
    assert exit_code == 2
    assert "unknown agent codename" in capsys.readouterr().err
    assert mock_set_mcp_server.call_count == 0


def test_disable_writer_file_not_found_exits_2(mock_set_mcp_server, capsys):
    mock_set_mcp_server.side_effect = FileNotFoundError(
        "openclaw.json not found at /home/x/.openclaw-intelligence/openclaw.json"
    )
    exit_code = main(["disable", "radar", "firefox"])
    assert exit_code == 2
    assert "openclaw.json not found" in capsys.readouterr().err


def test_disable_json_mode(mock_set_mcp_server, capsys):
    exit_code = main(["disable", "radar", "firefox", "--json"])
    assert exit_code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed == {
        "action": "disable",
        "agent_id": "radar",
        "server_name": "firefox",
        "status": "ok",
    }


# ---- end-to-end: real writer against a tmp openclaw.json -------------------


def test_enable_then_disable_roundtrip(monkeypatch, tmp_path, capsys):
    """Drives the REAL `set_mcp_server` (no mock) — the test that
    exercises the D1 direct-in-process-call decision end to end. The
    live AGENT_PATHS entry is patched to a tmp file (D6 seam).
    """
    cfg = tmp_path / "openclaw.json"
    cfg.write_text('{"mcp": {"servers": {}}}\n', encoding="utf-8")
    monkeypatch.setitem(openclaw_writer.AGENT_PATHS, "scout", cfg)

    rc = main([
        "enable", "scout", "firefox",
        "--config-json", '{"command": "firefox-mcp"}',
    ])
    assert rc == 0
    after_enable = json.loads(cfg.read_text(encoding="utf-8"))
    assert after_enable["mcp"]["servers"]["firefox"] == {"command": "firefox-mcp"}

    rc = main(["disable", "scout", "firefox"])
    assert rc == 0
    after_disable = json.loads(cfg.read_text(encoding="utf-8"))
    assert "firefox" not in after_disable["mcp"]["servers"]

    # The writer leaves a sibling .bak of the pre-write content.
    assert cfg.with_suffix(".json.bak").exists()


def test_disable_idempotent_already_absent(monkeypatch, tmp_path):
    """Disabling an absent server is a clean no-op exit 0 — the writer
    guarantees idempotency; the CLI surfaces it without error.
    """
    cfg = tmp_path / "openclaw.json"
    cfg.write_text('{"mcp": {"servers": {}}}\n', encoding="utf-8")
    monkeypatch.setitem(openclaw_writer.AGENT_PATHS, "bridge", cfg)

    assert main(["disable", "bridge", "never-was-here"]) == 0
    assert main(["disable", "bridge", "never-was-here"]) == 0
