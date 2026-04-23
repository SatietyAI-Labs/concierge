"""Unit tests for the X13 install module.

All tests mock `subprocess.run` — no actual install is performed.
Covers the three low-level installers, the OSError / TimeoutExpired
failure paths, the dispatcher's method-string normalization, and
the dispatcher's None-return path for unrecognized or under-
specified methods.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.install import (
    InstallResult,
    install_by_method,
    install_npm_global,
    install_npx_mcp,
    install_pip_user,
    install_single_binary,
    normalize_install_method,
)
from core.install.methods import (
    METHOD_NPM_GLOBAL,
    METHOD_NPX_MCP,
    METHOD_PIP_USER,
    METHOD_SINGLE_BINARY,
)


def _mock_completed(returncode=0, stdout="", stderr=""):
    completed = MagicMock()
    completed.returncode = returncode
    completed.stdout = stdout
    completed.stderr = stderr
    return completed


# ---- Low-level installers: success paths ---------------------------------


class TestInstallNpmGlobal:
    def test_success_returns_install_result_with_method_key(self):
        with patch("core.install.methods.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed(0, "+ ripgrep@14.0.0\n", "")
            result = install_npm_global("ripgrep")

        assert isinstance(result, InstallResult)
        assert result.method == METHOD_NPM_GLOBAL
        assert result.success is True
        assert result.returncode == 0
        assert "ripgrep@14.0.0" in result.stdout
        assert result.elapsed_ms >= 0

    def test_command_has_no_sudo_and_uses_global_flag(self):
        with patch("core.install.methods.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed(0)
            result = install_npm_global("ripgrep")

        # Command audit: npm install -g, never sudo
        assert "sudo" not in result.command
        assert "-g" in result.command
        assert "ripgrep" in result.command

        # Also verify the actual subprocess invocation args
        called_args = mock_run.call_args[0][0]
        assert called_args[0] == "npm"
        assert "sudo" not in called_args
        assert "-g" in called_args

    def test_non_zero_returncode_is_failure(self):
        with patch("core.install.methods.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed(1, "", "npm ERR! 404")
            result = install_npm_global("not-a-real-package-name-xyz")

        assert result.success is False
        assert result.returncode == 1
        assert "npm ERR" in result.stderr


class TestInstallNpxMcp:
    def test_success_returns_install_result_with_method_key(self):
        with patch("core.install.methods.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed(0, "@modelcontextprotocol/server-filesystem\n", "")
            result = install_npx_mcp("@modelcontextprotocol/server-filesystem")

        assert isinstance(result, InstallResult)
        assert result.method == METHOD_NPX_MCP
        assert result.success is True
        assert result.returncode == 0

    def test_command_uses_npm_view_not_sudo(self):
        with patch("core.install.methods.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed(0)
            result = install_npx_mcp("@scope/pkg")

        assert "sudo" not in result.command
        assert "npm" in result.command
        assert "view" in result.command
        called_args = mock_run.call_args[0][0]
        assert called_args == ["npm", "view", "@scope/pkg", "name"]

    def test_unknown_package_is_failure(self):
        with patch("core.install.methods.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed(1, "", "npm ERR! 404")
            result = install_npx_mcp("@scope/does-not-exist-xyz")

        assert result.success is False
        assert result.returncode == 1


class TestInstallPipUser:
    def test_success(self):
        with patch("core.install.methods.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed(0, "Successfully installed csvkit-1.0\n", "")
            result = install_pip_user("csvkit")

        assert result.method == METHOD_PIP_USER
        assert result.success is True
        assert "Successfully installed" in result.stdout

    def test_command_uses_user_flag_not_sudo(self):
        with patch("core.install.methods.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed(0)
            result = install_pip_user("csvkit")

        assert "--user" in result.command
        assert "sudo" not in result.command

        called_args = mock_run.call_args[0][0]
        assert called_args[0] == "pip"
        assert "--user" in called_args


class TestInstallSingleBinary:
    def test_success(self, tmp_path):
        dest = str(tmp_path / "my_binary")
        with patch("core.install.methods.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed(0, "", "")
            result = install_single_binary(
                "https://example.com/my_binary", dest
            )

        assert result.method == METHOD_SINGLE_BINARY
        assert result.success is True
        # command is a shell one-liner with both stages
        assert "curl" in result.command
        assert "chmod" in result.command

    def test_expands_home_in_dest_path(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch("core.install.methods.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed(0)
            install_single_binary(
                "https://example.com/bin", "~/bin/tool"
            )

        shell_cmd = mock_run.call_args[0][0]
        assert str(tmp_path / "bin" / "tool") in shell_cmd

    def test_creates_parent_dir_for_dest(self, tmp_path):
        dest_dir = tmp_path / "deep" / "nested" / "path"
        dest = str(dest_dir / "binary")
        assert not dest_dir.exists()

        with patch("core.install.methods.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed(0)
            install_single_binary("https://example.com/bin", dest)

        assert dest_dir.exists()

    def test_shlex_quotes_url_and_dest(self):
        with patch("core.install.methods.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed(0)
            # URL with shell-metacharacter would be a command-injection
            # risk if not shlex-quoted. The test verifies the quoting
            # happens inside the rendered shell command.
            install_single_binary(
                "https://example.com/evil$(echo pwned)",
                "/tmp/dest",
            )

        shell_cmd = mock_run.call_args[0][0]
        # The dangerous substring must be single-quoted so shell
        # won't evaluate it. shlex.quote single-quotes and escapes
        # internal single quotes.
        assert "'https://example.com/evil$(echo pwned)'" in shell_cmd


# ---- Failure-class handling ---------------------------------------------


class TestInstallFailurePaths:
    def test_command_not_found_collapses_to_returncode_minus_one(self):
        with patch("core.install.methods.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("No such file or directory: 'npm'")
            result = install_npm_global("ripgrep")

        assert result.success is False
        assert result.returncode == -1
        assert "command not found" in result.stderr
        assert result.elapsed_ms >= 0

    def test_timeout_collapses_to_returncode_minus_one(self):
        with patch("core.install.methods.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["pip", "install", "--user", "slow-package"],
                timeout=60,
                output=b"partial output\n",
                stderr=b"partial stderr\n",
            )
            result = install_pip_user("slow-package", timeout_seconds=60)

        assert result.success is False
        assert result.returncode == -1
        assert "timed out" in result.stderr
        assert "partial output" in result.stdout
        assert "partial stderr" in result.stderr

    def test_os_error_collapses_to_returncode_minus_one(self):
        with patch("core.install.methods.subprocess.run") as mock_run:
            mock_run.side_effect = OSError("permission denied on install dir")
            result = install_pip_user("csvkit")

        assert result.success is False
        assert result.returncode == -1
        assert "OSError" in result.stderr
        assert "permission denied" in result.stderr

    def test_single_binary_os_error_handling(self, tmp_path):
        dest = str(tmp_path / "bin")
        with patch("core.install.methods.subprocess.run") as mock_run:
            mock_run.side_effect = OSError("bad shell")
            result = install_single_binary("https://example.com/x", dest)

        assert result.success is False
        assert result.returncode == -1
        assert "OSError" in result.stderr


# ---- normalize_install_method dispatch -----------------------------------


class TestNormalizeInstallMethod:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("npm -g", METHOD_NPM_GLOBAL),
            ("npm install -g", METHOD_NPM_GLOBAL),
            ("npm global", METHOD_NPM_GLOBAL),
            ("NPM -G", METHOD_NPM_GLOBAL),
            ("npm_global", METHOD_NPM_GLOBAL),
            ("npx", METHOD_NPX_MCP),
            ("npx -y @scope/pkg", METHOD_NPX_MCP),
            ("npx-mcp", METHOD_NPX_MCP),
            ("npx_mcp", METHOD_NPX_MCP),
            ("NPX -Y @scope/pkg", METHOD_NPX_MCP),
            ("pip --user", METHOD_PIP_USER),
            ("pip install --user", METHOD_PIP_USER),
            ("pip user", METHOD_PIP_USER),
            ("PIP --USER", METHOD_PIP_USER),
            ("single binary", METHOD_SINGLE_BINARY),
            ("binary", METHOD_SINGLE_BINARY),
            ("curl download", METHOD_SINGLE_BINARY),
            ("download", METHOD_SINGLE_BINARY),
        ],
    )
    def test_known_methods_canonicalize(self, raw, expected):
        assert normalize_install_method(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "  ",
            "apt install",
            "brew install",
            "snap install",
            "cargo install",  # NOT in X13 scope — future extension
            "go install",
            "docker pull",
        ],
    )
    def test_unknown_methods_return_none(self, raw):
        assert normalize_install_method(raw) is None

    def test_none_input_returns_none(self):
        assert normalize_install_method(None) is None


# ---- install_by_method dispatcher ---------------------------------------


class TestInstallByMethod:
    def test_routes_npm_to_install_npm_global(self):
        with patch("core.install.service.install_npm_global") as mock_npm:
            mock_npm.return_value = InstallResult(
                method=METHOD_NPM_GLOBAL,
                command="npm install -g ripgrep",
                success=True,
                returncode=0,
                stdout="",
                stderr="",
                elapsed_ms=100,
            )
            result = install_by_method("npm -g", tool_name="ripgrep")

        mock_npm.assert_called_once_with("ripgrep")
        assert result.method == METHOD_NPM_GLOBAL
        assert result.success is True

    def test_routes_npx_to_install_npx_mcp(self):
        with patch("core.install.service.install_npx_mcp") as mock_npx:
            mock_npx.return_value = InstallResult(
                method=METHOD_NPX_MCP,
                command="npm view @scope/pkg name",
                success=True,
                returncode=0,
                stdout="@scope/pkg",
                stderr="",
                elapsed_ms=100,
            )
            result = install_by_method("npx -y @scope/pkg", tool_name="@scope/pkg")

        mock_npx.assert_called_once_with("@scope/pkg")
        assert result.method == METHOD_NPX_MCP
        assert result.success is True

    def test_routes_pip_to_install_pip_user(self):
        with patch("core.install.service.install_pip_user") as mock_pip:
            mock_pip.return_value = InstallResult(
                method=METHOD_PIP_USER,
                command="pip install --user csvkit",
                success=True,
                returncode=0,
                stdout="",
                stderr="",
                elapsed_ms=100,
            )
            result = install_by_method("pip --user", tool_name="csvkit")

        mock_pip.assert_called_once_with("csvkit")
        assert result.method == METHOD_PIP_USER

    def test_routes_single_binary_with_url_and_dest(self):
        with patch("core.install.service.install_single_binary") as mock_bin:
            mock_bin.return_value = InstallResult(
                method=METHOD_SINGLE_BINARY,
                command="curl ... && chmod +x",
                success=True,
                returncode=0,
                stdout="",
                stderr="",
                elapsed_ms=100,
            )
            result = install_by_method(
                "single binary",
                tool_name="xsv",
                binary_url="https://example.com/xsv",
                binary_dest="~/bin/xsv",
            )

        mock_bin.assert_called_once_with(
            "https://example.com/xsv", "~/bin/xsv"
        )
        assert result.method == METHOD_SINGLE_BINARY

    def test_unrecognized_method_returns_none(self):
        result = install_by_method("apt install", tool_name="ripgrep")
        assert result is None

    def test_single_binary_without_url_returns_none(self):
        # Missing binary_url → dispatcher declines, returns None
        result = install_by_method(
            "single binary", tool_name="xsv", binary_dest="~/bin/xsv"
        )
        assert result is None

    def test_single_binary_without_dest_returns_none(self):
        result = install_by_method(
            "single binary", tool_name="xsv", binary_url="https://example.com/xsv"
        )
        assert result is None

    def test_timeout_override_passes_through_to_installer(self):
        with patch("core.install.service.install_npm_global") as mock_npm:
            mock_npm.return_value = InstallResult(
                method=METHOD_NPM_GLOBAL,
                command="",
                success=True,
                returncode=0,
                stdout="",
                stderr="",
                elapsed_ms=0,
            )
            install_by_method("npm -g", tool_name="ripgrep", timeout_seconds=5.0)

        mock_npm.assert_called_once_with("ripgrep", timeout_seconds=5.0)

    def test_empty_install_method_returns_none(self):
        assert install_by_method("", tool_name="x") is None

    def test_none_like_install_method_returns_none(self):
        # An empty / whitespace-only string short-circuits through
        # normalize_install_method to None and the dispatcher
        # declines. Caller handles as operator-must-install.
        assert install_by_method("   ", tool_name="x") is None
