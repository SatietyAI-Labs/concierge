"""Tests for core.agent_config.openclaw_writer — Stage 1A item 6.

Covers the writer's six failure modes, the .bak rotation discipline,
the structural preservation rules, and the agent-codename
exhaustiveness guard.

The writer's `config_path` keyword arg accepts a tmp_path-backed
override so these tests never touch the live AGENT_PATHS targets
(`~/.openclaw/openclaw.json` etc.). Live-path resolution is exercised
separately via the AGENT_PATHS structural tests — those don't read
or write any file.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from core.agent_config.openclaw_writer import (
    AGENT_PATHS,
    AGENT_ROOTS,
    UnknownAgentError,
    set_mcp_server,
)


# ---- Helpers ---------------------------------------------------------------


def _seed_config(path: Path, mcp_servers: dict | None = None) -> None:
    """Write a minimal openclaw.json shape with optional pre-seeded
    mcp.servers content. Mirrors the shape of the live configs
    inspected during the items-5+6 plan-surface (2026-05-14).
    """
    body: dict = {
        "meta": {"lastTouchedVersion": "2026.4.12"},
        "auth": {"profiles": {"anthropic:claude": {"provider": "anthropic"}}},
    }
    if mcp_servers is not None:
        body["mcp"] = {"servers": mcp_servers}
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---- AGENT_PATHS exhaustiveness + path correctness -------------------------


class TestAgentPaths:
    """`AGENT_PATHS` is the agent-codename surface for `set_mcp_server`.
    Growth here (new agent joining the fleet) needs to land in lock-
    step with the consumer surface — these tests pin the set so a
    rename or addition surfaces in test runs.
    """

    def test_covers_exactly_the_five_codenames(self):
        assert set(AGENT_PATHS.keys()) == {
            "alfred", "scout", "dispatch", "radar", "bridge",
        }

    def test_codename_to_functional_path_translation(self):
        """Codenames map to the functional-name directories per
        CLAUDE.md §2. Functional names (not codenames) live on disk.
        """
        home = Path.home()
        assert AGENT_PATHS["alfred"] == home / ".openclaw" / "openclaw.json"
        assert AGENT_PATHS["scout"] == home / ".openclaw-content" / "openclaw.json"
        assert AGENT_PATHS["dispatch"] == home / ".openclaw-distribution" / "openclaw.json"
        assert AGENT_PATHS["radar"] == home / ".openclaw-intelligence" / "openclaw.json"
        assert AGENT_PATHS["bridge"] == home / ".openclaw-engagement" / "openclaw.json"

    def test_every_path_ends_in_openclaw_json(self):
        for codename, path in AGENT_PATHS.items():
            assert path.name == "openclaw.json", (
                f"agent {codename} resolved to non-openclaw.json path: {path}"
            )


class TestAgentRoots:
    """`AGENT_ROOTS` (Stage 1A item 8 D2) is the package's canonical
    codename↔functional-name registry. `AGENT_PATHS` is derived from
    it; the identity-notes migration derives `<root>/workspace/
    IDENTITY.md` from it. The two maps must not drift.
    """

    def test_covers_exactly_the_five_codenames(self):
        assert set(AGENT_ROOTS.keys()) == {
            "alfred", "scout", "dispatch", "radar", "bridge",
        }

    def test_root_to_functional_translation(self):
        home = Path.home()
        assert AGENT_ROOTS["alfred"] == home / ".openclaw"
        assert AGENT_ROOTS["scout"] == home / ".openclaw-content"
        assert AGENT_ROOTS["dispatch"] == home / ".openclaw-distribution"
        assert AGENT_ROOTS["radar"] == home / ".openclaw-intelligence"
        assert AGENT_ROOTS["bridge"] == home / ".openclaw-engagement"

    def test_agent_paths_are_derived_from_roots(self):
        """`AGENT_PATHS` values stay byte-identical to
        `<root>/openclaw.json` — derivation, not a second literal map.
        """
        assert set(AGENT_PATHS.keys()) == set(AGENT_ROOTS.keys())
        for codename, root in AGENT_ROOTS.items():
            assert AGENT_PATHS[codename] == root / "openclaw.json"


# ---- Enable (insert / replace) ---------------------------------------------


class TestEnable:
    def test_inserts_new_server(self, tmp_path):
        cfg = tmp_path / "openclaw.json"
        _seed_config(cfg, mcp_servers={"memory": {"command": "/bin/sh"}})

        set_mcp_server(
            "alfred",
            "firefox",
            {"command": "npx", "args": ["firefox-devtools-mcp@latest"]},
            config_path=cfg,
        )

        result = _read(cfg)
        assert result["mcp"]["servers"]["firefox"] == {
            "command": "npx",
            "args": ["firefox-devtools-mcp@latest"],
        }
        # Existing server preserved.
        assert result["mcp"]["servers"]["memory"] == {"command": "/bin/sh"}
        # Sibling top-level keys preserved.
        assert "auth" in result
        assert result["meta"]["lastTouchedVersion"] == "2026.4.12"

    def test_replaces_existing_server(self, tmp_path):
        cfg = tmp_path / "openclaw.json"
        _seed_config(cfg, mcp_servers={"memory": {"command": "/bin/sh", "args": []}})

        set_mcp_server(
            "alfred",
            "memory",
            {"command": "/usr/bin/python", "args": ["-m", "memory"]},
            config_path=cfg,
        )

        result = _read(cfg)
        assert result["mcp"]["servers"]["memory"] == {
            "command": "/usr/bin/python",
            "args": ["-m", "memory"],
        }
        # No accidental "memory.old" or merge — full replacement.
        assert list(result["mcp"]["servers"].keys()) == ["memory"]

    def test_mcp_servers_absent_creates_nested_dict(self, tmp_path):
        """Fresh config with no `mcp` key gets the full structure
        built on first enable. No KeyError, no need for the operator
        to pre-seed mcp.servers.
        """
        cfg = tmp_path / "openclaw.json"
        cfg.write_text(json.dumps({"meta": {}}) + "\n", encoding="utf-8")

        set_mcp_server(
            "scout",
            "memory",
            {"command": "/bin/sh", "env": {"MOLTBOT_MEMORY_DIR": "/tmp/x"}},
            config_path=cfg,
        )

        result = _read(cfg)
        assert "mcp" in result
        assert "servers" in result["mcp"]
        assert result["mcp"]["servers"]["memory"]["command"] == "/bin/sh"

    def test_server_config_treated_as_opaque(self, tmp_path):
        """The writer is content-agnostic about server_config — it
        does not validate shape, normalize keys, or assume MCP-specific
        structure. Items-5+6 scope clarification: Concierge's surface
        is category-neutral; even though THIS writer is mcp.servers-
        scoped, the dict it installs is whatever the caller passes.
        """
        cfg = tmp_path / "openclaw.json"
        _seed_config(cfg)

        unusual_payload = {
            "command": "node",
            "args": ["/some/path"],
            "custom_field_the_writer_does_not_care_about": True,
            "nested": {"deeply": {"shaped": "data"}},
        }
        set_mcp_server("bridge", "experimental", unusual_payload, config_path=cfg)

        result = _read(cfg)
        assert result["mcp"]["servers"]["experimental"] == unusual_payload


# ---- Disable (remove) ------------------------------------------------------


class TestDisable:
    def test_removes_existing_server(self, tmp_path):
        cfg = tmp_path / "openclaw.json"
        _seed_config(cfg, mcp_servers={
            "memory": {"command": "/bin/sh"},
            "firefox": {"command": "npx"},
        })

        set_mcp_server("alfred", "firefox", None, config_path=cfg)

        result = _read(cfg)
        assert "firefox" not in result["mcp"]["servers"]
        # Sibling server preserved.
        assert "memory" in result["mcp"]["servers"]

    def test_is_idempotent_on_absent_server(self, tmp_path, caplog):
        """Disabling a server that's already absent is a pure no-op:
        no write, no .bak rotation. The pre-existing state is the
        operator's baseline and stays untouched.
        """
        cfg = tmp_path / "openclaw.json"
        _seed_config(cfg, mcp_servers={"memory": {"command": "/bin/sh"}})
        bak = cfg.with_suffix(cfg.suffix + ".bak")
        mtime_before = cfg.stat().st_mtime_ns

        import logging
        caplog.set_level(logging.INFO, logger="core.agent_config.openclaw_writer")
        set_mcp_server("alfred", "never-existed", None, config_path=cfg)

        # File unchanged.
        assert cfg.stat().st_mtime_ns == mtime_before
        # No .bak created — no rotation happened.
        assert not bak.exists()
        # INFO log records the no-op for operator visibility.
        assert any("disable_noop" in rec.message for rec in caplog.records)

    def test_removing_last_server_leaves_empty_servers_dict(self, tmp_path):
        """Structural preservation — removing the only server doesn't
        delete the `mcp.servers` key. Future readers (config inspectors,
        grep-based smoke checks) can rely on the structural shape
        regardless of how empty it is.
        """
        cfg = tmp_path / "openclaw.json"
        _seed_config(cfg, mcp_servers={"memory": {"command": "/bin/sh"}})

        set_mcp_server("alfred", "memory", None, config_path=cfg)

        result = _read(cfg)
        assert "mcp" in result
        assert "servers" in result["mcp"]
        assert result["mcp"]["servers"] == {}


# ---- Failure modes ---------------------------------------------------------


class TestFailureModes:
    def test_missing_config_file_raises_file_not_found(self, tmp_path):
        cfg = tmp_path / "does-not-exist.json"

        with pytest.raises(FileNotFoundError, match="openclaw.json not found"):
            set_mcp_server(
                "alfred", "memory", {"command": "/bin/sh"}, config_path=cfg
            )

    def test_malformed_json_raises_with_path_in_message(self, tmp_path):
        cfg = tmp_path / "openclaw.json"
        cfg.write_text("{ this is not, valid JSON ]]]", encoding="utf-8")

        with pytest.raises(json.JSONDecodeError) as exc_info:
            set_mcp_server(
                "alfred", "memory", {"command": "/bin/sh"}, config_path=cfg
            )

        # The path is appended to the error message for operator triage —
        # an operator reading the error doesn't need to inspect the
        # traceback frames to find which file failed to parse.
        assert str(cfg) in str(exc_info.value)

    def test_unknown_agent_id_raises(self, tmp_path):
        """When no config_path is passed, the writer resolves via
        AGENT_PATHS. Unknown agent_id should fail loudly with a clear
        message — distinct from FileNotFoundError so the caller can
        tell "wrong agent name" from "file missing."
        """
        with pytest.raises(UnknownAgentError, match="not in the AGENT_PATHS set"):
            set_mcp_server("unknown-agent", "memory", {"command": "/bin/sh"})

    def test_atomic_write_failure_cleans_up_temp(self, tmp_path, monkeypatch):
        """If `os.replace` fails mid-write, the tempfile must not
        linger. Operators inspecting the directory after a failed
        run should see nothing more than the original file + (if it
        was rotated) the .bak — no orphaned .openclaw.json.*.tmp
        files.
        """
        cfg = tmp_path / "openclaw.json"
        _seed_config(cfg, mcp_servers={"memory": {"command": "/bin/sh"}})

        original_replace = os.replace
        target_str = str(cfg)

        def flaky_replace(src, dst, *args, **kwargs):
            # Fail only when replacing the config (not the .bak write).
            if str(dst) == target_str:
                raise OSError("simulated replace failure")
            return original_replace(src, dst, *args, **kwargs)

        monkeypatch.setattr(os, "replace", flaky_replace)

        with pytest.raises(OSError, match="simulated replace failure"):
            set_mcp_server(
                "alfred", "firefox", {"command": "npx"}, config_path=cfg
            )

        # No leftover tempfiles in the directory.
        leftover_tmps = list(tmp_path.glob(".openclaw.json.*.tmp"))
        assert leftover_tmps == [], (
            f"tempfile cleanup failed; leftover: {leftover_tmps}"
        )


# ---- .bak rotation discipline ----------------------------------------------


class TestBakRotation:
    def test_bak_created_with_previous_content(self, tmp_path):
        """Pre-write content lands in `.bak`. Operator can read the
        sibling to see what the file looked like before the most
        recent change.
        """
        cfg = tmp_path / "openclaw.json"
        _seed_config(cfg, mcp_servers={"memory": {"command": "/bin/sh"}})
        previous_content = cfg.read_text(encoding="utf-8")

        set_mcp_server(
            "alfred", "firefox", {"command": "npx"}, config_path=cfg,
        )

        bak = cfg.with_suffix(cfg.suffix + ".bak")
        assert bak.exists()
        assert bak.read_text(encoding="utf-8") == previous_content

    def test_bak_overwritten_on_subsequent_write(self, tmp_path):
        """Only the most-recent `.bak` survives. The long-term audit
        trail is per-stage snapshots, not per-write timestamped
        backups (items-5+6 Decision 8).
        """
        cfg = tmp_path / "openclaw.json"
        _seed_config(cfg, mcp_servers={"memory": {"command": "/bin/sh"}})

        # First write — .bak captures the initial state.
        set_mcp_server("alfred", "firefox", {"command": "npx"}, config_path=cfg)
        bak = cfg.with_suffix(cfg.suffix + ".bak")
        first_bak_content = bak.read_text(encoding="utf-8")
        assert "firefox" not in first_bak_content  # initial state had no firefox

        # Second write — .bak now captures the post-first-write state,
        # not the original.
        set_mcp_server(
            "alfred", "browser-control", {"command": "node"}, config_path=cfg,
        )
        second_bak_content = bak.read_text(encoding="utf-8")
        assert "firefox" in second_bak_content  # rotation happened
        assert "browser-control" not in second_bak_content  # bak is pre-write

    def test_bak_not_written_on_idempotent_disable(self, tmp_path):
        """Disable-noop produces no write, so no `.bak` rotation either —
        otherwise the operator would lose their previous .bak to a
        function call that didn't actually change anything.
        """
        cfg = tmp_path / "openclaw.json"
        _seed_config(cfg, mcp_servers={"memory": {"command": "/bin/sh"}})

        # First, create a meaningful .bak via an enable.
        set_mcp_server("alfred", "firefox", {"command": "npx"}, config_path=cfg)
        bak = cfg.with_suffix(cfg.suffix + ".bak")
        meaningful_bak = bak.read_text(encoding="utf-8")
        assert "firefox" not in meaningful_bak  # captured pre-enable state

        # Now a disable-noop on an absent server. The meaningful .bak
        # must survive — no rotation triggered by the no-op.
        set_mcp_server("alfred", "never-existed", None, config_path=cfg)
        assert bak.read_text(encoding="utf-8") == meaningful_bak
