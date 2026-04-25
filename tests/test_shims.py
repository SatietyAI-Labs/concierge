"""Unit tests for `core.install.shims` — Day 6 Option 3 shim-script
generator + PATH-visibility checker.

Per DECISIONS `[2026-04-27 Day 6]` Decision A:

- Shim location is `~/.concierge/bin/` (unambiguously Concierge-owned)
- Shim is a bash one-liner that exec's `<venv>/bin/<tool>` with `"$@"`
  passthrough; chmod 0o755
- Shell detection is intentionally narrow: bash → `~/.bashrc`,
  zsh → `~/.zshrc`, anything else → `~/.profile` with an explanatory
  note. Fish/nushell/PowerShell are NOT auto-detected (regression
  guard test below).
- A future contributor MUST NOT expand the shell-detection helper
  without a real-world signal — Decision A is explicit about that.

All tests are filesystem-touching but use `tmp_path` as the operator's
home so `~/.concierge/` is never written to during test runs.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from core.install.shims import _check_path_visibility, _generate_shim


# ---- Shim generation ------------------------------------------------------


class TestGenerateShim:
    """Shim is a bash one-liner that exec's the venv-installed binary
    with full positional + named arg passthrough. Operator invokes the
    tool by name; the shim is the indirection layer.
    """

    def test_writes_executable_bash_one_liner(self, tmp_path):
        """The generated shim is a 2-3 line bash script: shebang +
        exec line. Chmod 0o755 so the operator can invoke directly.
        """
        venv = tmp_path / ".concierge" / "tools-venv"
        (venv / "bin").mkdir(parents=True)
        (venv / "bin" / "csvkit").write_text("#!/usr/bin/env python3\n")
        (venv / "bin" / "csvkit").chmod(0o755)

        shim_path = _generate_shim("csvkit", venv, home=tmp_path)

        assert shim_path == tmp_path / ".concierge" / "bin" / "csvkit"
        assert shim_path.exists()

        # File is executable (mode bits include user/group/other +x)
        mode = shim_path.stat().st_mode
        assert mode & stat.S_IXUSR, "shim must be user-executable"
        assert mode & stat.S_IXGRP, "shim must be group-executable"
        assert mode & stat.S_IXOTH, "shim must be other-executable"

        content = shim_path.read_text()
        # Shebang
        assert content.startswith("#!/usr/bin/env bash\n")
        # exec line that targets the venv binary
        expected_target = str(venv / "bin" / "csvkit")
        assert f'exec "{expected_target}" "$@"' in content, (
            f"shim must exec the venv binary with full arg passthrough; "
            f"content was:\n{content}"
        )

    def test_creates_bin_dir_if_missing(self, tmp_path):
        """Fresh operator: `~/.concierge/bin/` doesn't exist yet.
        Generator creates it via mkdir(parents=True, exist_ok=True).
        """
        bin_dir = tmp_path / ".concierge" / "bin"
        assert not bin_dir.exists()

        venv = tmp_path / ".concierge" / "tools-venv"
        _generate_shim("csvkit", venv, home=tmp_path)

        assert bin_dir.is_dir()

    def test_idempotent_overwrite(self, tmp_path):
        """Re-installing a tool (e.g. operator approves a new version)
        overwrites the existing shim cleanly. No errors, no append-style
        corruption.
        """
        venv = tmp_path / ".concierge" / "tools-venv"

        # First generation
        first = _generate_shim("csvkit", venv, home=tmp_path)
        first_content = first.read_text()
        first_mtime = first.stat().st_mtime_ns

        # Second generation with same args — should overwrite, not error
        second = _generate_shim("csvkit", venv, home=tmp_path)

        assert second == first
        # Content matches (same args produce same shim)
        assert second.read_text() == first_content
        # Still executable
        assert second.stat().st_mode & stat.S_IXUSR


# ---- PATH-visibility check (Decision A's runtime warning) ----------------


class TestPathVisibility:
    """install_pip_user emits a warning in InstallResult.stderr when
    `~/.concierge/bin/` isn't on PATH. The warning includes a copy-
    pasteable shell-detected PATH-addition instruction.

    Shell detection: bash → `~/.bashrc`, zsh → `~/.zshrc`, anything
    else → `~/.profile` with an "if your shell doesn't read ~/.profile,
    add this line to your shell's startup file" note.
    """

    def test_returns_none_when_on_path(self, tmp_path, monkeypatch):
        """When `~/.concierge/bin/` is on PATH, no warning needed.
        """
        bin_dir = tmp_path / ".concierge" / "bin"
        bin_dir.mkdir(parents=True)
        # Put bin_dir on PATH
        monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")

        result = _check_path_visibility(home=tmp_path)

        assert result is None, (
            f"Expected None when bin_dir is on PATH; got {result!r}"
        )

    def test_returns_warning_when_off_path(self, tmp_path, monkeypatch):
        """When `~/.concierge/bin/` is NOT on PATH, returns a warning
        string with the bin_dir path embedded so the operator can
        copy-paste it into their shell rc.
        """
        monkeypatch.setenv("PATH", "/usr/bin:/bin")

        result = _check_path_visibility(home=tmp_path)

        assert result is not None
        assert str(tmp_path / ".concierge" / "bin") in result, (
            "Warning must embed the bin_dir path so operator knows what "
            "to add"
        )
        # The warning is a single coherent message (not multi-section)
        assert "PATH" in result

    def test_uses_bashrc_for_bash_shell(self, tmp_path, monkeypatch):
        """$SHELL=/bin/bash → PATH-addition instruction targets
        ~/.bashrc.
        """
        monkeypatch.setenv("PATH", "/usr/bin:/bin")
        monkeypatch.setenv("SHELL", "/bin/bash")

        result = _check_path_visibility(home=tmp_path)

        assert result is not None
        assert "~/.bashrc" in result or ".bashrc" in result
        # bash-rc instruction does NOT carry the "your shell may not
        # read this" fallback note — that's only for the catch-all
        assert "may not read" not in result

    def test_uses_zshrc_for_zsh_shell(self, tmp_path, monkeypatch):
        """$SHELL=/bin/zsh → PATH-addition instruction targets
        ~/.zshrc.
        """
        monkeypatch.setenv("PATH", "/usr/bin:/bin")
        monkeypatch.setenv("SHELL", "/bin/zsh")

        result = _check_path_visibility(home=tmp_path)

        assert result is not None
        assert "~/.zshrc" in result or ".zshrc" in result
        assert "may not read" not in result

    def test_falls_back_to_profile_for_unrecognized_shell(
        self, tmp_path, monkeypatch
    ):
        """Decision A regression guard: an unrecognized shell name
        (fish, nushell, PowerShell, anything else) maps to ~/.profile
        with the explanatory "your shell may not read this" note —
        NOT a guess at the shell's rc file. Fish-specific config.fish
        support is explicitly out of scope until a real-world signal
        justifies it (per the DECISIONS entry's "MUST NOT expand
        without real-world signal").
        """
        monkeypatch.setenv("PATH", "/usr/bin:/bin")
        monkeypatch.setenv("SHELL", "/usr/local/bin/fish")

        result = _check_path_visibility(home=tmp_path)

        assert result is not None
        assert "~/.profile" in result or ".profile" in result, (
            "Unrecognized shell must fall back to ~/.profile, not "
            f"a per-shell config file. Result was: {result!r}"
        )
        # The fallback explanatory note must be present so the
        # operator knows their shell may not read ~/.profile
        assert "may not read" in result.lower() or "shell's startup" in result.lower(), (
            "Fallback message must include the 'your shell may not read "
            "this' note so operator knows to handle it themselves; got: "
            f"{result!r}"
        )
        # Specifically: NOT a guess at fish's config.fish
        assert "config.fish" not in result, (
            "Decision A: fish-specific detection is out of scope; "
            "fallback message must not mention config.fish"
        )

    def test_falls_back_to_profile_when_shell_unset(
        self, tmp_path, monkeypatch
    ):
        """No $SHELL env var (e.g. non-interactive context, container
        runtime). Falls back to ~/.profile + explanatory note.
        """
        monkeypatch.setenv("PATH", "/usr/bin:/bin")
        monkeypatch.delenv("SHELL", raising=False)

        result = _check_path_visibility(home=tmp_path)

        assert result is not None
        assert "~/.profile" in result or ".profile" in result
        assert "may not read" in result.lower() or "shell's startup" in result.lower()
