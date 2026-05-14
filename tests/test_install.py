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
    install_pipx,
    install_single_binary,
    normalize_install_method,
)
from core.install.methods import (
    METHOD_NPM_GLOBAL,
    METHOD_NPX_MCP,
    METHOD_PIP_USER,
    METHOD_PIPX,
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
    """install_pip_user installs into the Concierge-managed venv at
    `~/.concierge/tools-venv/` (Day 6 Option 3, DECISIONS
    `[2026-04-27 Day 6]`). Tests mock four collaborators:

    - `_ensure_concierge_venv` — returns a fake venv path under
      tmp_path so the helper has its own dedicated test surface in
      `tests/test_venv_bootstrap.py`
    - `subprocess.run` — executes the pip install
    - `_generate_shim` — writes the operator-facing shim at
      `~/.concierge/bin/<tool>`; dedicated test surface in
      `tests/test_shims.py`
    - `_check_path_visibility` — emits the warning if `~/.concierge/bin/`
      is not on PATH; dedicated test surface in `tests/test_shims.py`

    Mocking all four keeps the test focused on `install_pip_user`'s
    orchestration logic without writing to real `~/.concierge/`.
    """

    def test_success(self, tmp_path):
        fake_venv = tmp_path / ".concierge" / "tools-venv"
        with patch("core.install.methods._ensure_concierge_venv") as mock_ensure, \
             patch("core.install.methods.subprocess.run") as mock_run, \
             patch("core.install.methods._generate_shim") as mock_shim, \
             patch("core.install.methods._check_path_visibility") as mock_path:
            mock_ensure.return_value = fake_venv
            mock_run.return_value = _mock_completed(0, "Successfully installed csvkit-1.0\n", "")
            mock_path.return_value = None  # PATH is fine, no warning
            result = install_pip_user("csvkit")

        assert result.method == METHOD_PIP_USER
        assert result.success is True
        assert "Successfully installed" in result.stdout
        # Helper consulted exactly once (lazy bootstrap)
        assert mock_ensure.call_count == 1
        # Shim generated post-install (Decision A contract)
        assert mock_shim.call_count == 1
        shim_args, shim_kwargs = mock_shim.call_args
        assert shim_args == ("csvkit", fake_venv)
        # PATH visibility checked
        assert mock_path.call_count == 1

    def test_command_uses_venv_pip_not_system_pip(self, tmp_path):
        """Day 6 Option 3 contract: install goes through the
        Concierge-managed venv's pip, not system `pip --user`.
        PEP-668 is sidestepped because the venv isn't system Python
        in the first place — no `--user` flag needed.
        """
        fake_venv = tmp_path / ".concierge" / "tools-venv"
        with patch("core.install.methods._ensure_concierge_venv") as mock_ensure, \
             patch("core.install.methods.subprocess.run") as mock_run, \
             patch("core.install.methods._generate_shim"), \
             patch("core.install.methods._check_path_visibility") as mock_path:
            mock_ensure.return_value = fake_venv
            mock_run.return_value = _mock_completed(0)
            mock_path.return_value = None
            result = install_pip_user("csvkit")

        # argv structure: [<venv>/bin/pip, "install", "csvkit"]
        called_args = mock_run.call_args[0][0]
        assert called_args[0] == str(fake_venv / "bin" / "pip"), (
            f"argv[0] must be <venv>/bin/pip; got {called_args[0]!r}. "
            f"Day 6 Option 3 routes pip through the Concierge-managed "
            f"venv, not system pip."
        )
        assert called_args[1] == "install"
        assert called_args[2] == "csvkit"
        # No --user flag — venv is already isolated; --user would be
        # meaningless inside a venv
        assert "--user" not in called_args
        assert "sudo" not in result.command

    def test_venv_bootstrap_failure_returns_install_failure(self, tmp_path):
        """Day 6 Option 3: when `_ensure_concierge_venv` raises
        ConciergeVenvError (e.g. stdlib venv missing, disk full,
        partial venv state), install_pip_user catches and converts
        to InstallResult(success=False, ...) per the existing X13
        "subprocess failures collapse to typed failure objects" rule.
        Caller (install_by_method, then lifecycle service) sees the
        same typed-failure shape regardless of whether the failure
        is in venv bootstrap or in the actual pip subprocess.
        """
        from core.install.venv import ConciergeVenvError
        with patch("core.install.methods._ensure_concierge_venv") as mock_ensure, \
             patch("core.install.methods.subprocess.run") as mock_run, \
             patch("core.install.methods._generate_shim") as mock_shim:
            mock_ensure.side_effect = ConciergeVenvError(
                "Concierge venv bootstrap failed (returncode=1): "
                "Error: Python 3.4+ required for venv module"
            )
            result = install_pip_user("csvkit")

        # subprocess.run was never called — bootstrap failed first
        assert mock_run.call_count == 0
        # Shim never generated — install never succeeded
        assert mock_shim.call_count == 0
        # Typed failure result, not a raised exception
        assert result.method == METHOD_PIP_USER
        assert result.success is False
        assert result.returncode == -1
        # Stderr carries the bootstrap diagnostic for operator audit
        assert "venv bootstrap failed" in result.stderr
        assert "Python 3.4+ required" in result.stderr

    def test_path_visibility_warning_appended_to_stderr_on_success(self, tmp_path):
        """Decision A contract: when ~/.concierge/bin/ is not on PATH,
        the install still succeeds but the InstallResult.stderr carries
        a one-line warning so the operator sees it via the lifecycle
        markdown / install record. Per-install warning makes silent
        invisibility impossible.
        """
        fake_venv = tmp_path / ".concierge" / "tools-venv"
        with patch("core.install.methods._ensure_concierge_venv") as mock_ensure, \
             patch("core.install.methods.subprocess.run") as mock_run, \
             patch("core.install.methods._generate_shim"), \
             patch("core.install.methods._check_path_visibility") as mock_path:
            mock_ensure.return_value = fake_venv
            mock_run.return_value = _mock_completed(0, "Successfully installed csvkit-1.0\n", "")
            mock_path.return_value = (
                "note: /home/op/.concierge/bin not on PATH; ..."
            )
            result = install_pip_user("csvkit")

        # Install still successful — warning is non-fatal
        assert result.success is True
        # Stderr carries the PATH warning
        assert "not on PATH" in result.stderr

    def test_shim_generation_failure_does_not_fail_the_install(self, tmp_path):
        """Shim generation failure is non-fatal — pip install already
        succeeded, the operator's tool is in the venv. They just won't
        be able to invoke it by name until the shim issue is resolved.
        Diagnostic appended to stderr; install marked successful.
        """
        fake_venv = tmp_path / ".concierge" / "tools-venv"
        with patch("core.install.methods._ensure_concierge_venv") as mock_ensure, \
             patch("core.install.methods.subprocess.run") as mock_run, \
             patch("core.install.methods._generate_shim") as mock_shim, \
             patch("core.install.methods._check_path_visibility") as mock_path:
            mock_ensure.return_value = fake_venv
            mock_run.return_value = _mock_completed(0, "Successfully installed csvkit-1.0\n", "")
            mock_shim.side_effect = OSError("disk full")
            mock_path.return_value = None
            result = install_pip_user("csvkit")

        # Install still successful — shim failure is non-fatal
        assert result.success is True
        # Stderr carries the shim diagnostic
        assert "shim generation failed" in result.stderr
        assert "disk full" in result.stderr


class TestInstallPipx:
    """install_pipx wraps `pipx install <package>`. pipx itself
    creates the per-package venv and places binaries on PATH; the
    handler is a thin subprocess wrapper, no shim or venv machinery
    on the Concierge side. Pattern matches TestInstallNpmGlobal /
    TestInstallNpxMcp.
    """

    def test_success_returns_install_result_with_method_key(self):
        with patch("core.install.methods.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed(
                0, "installed package csvkit 1.3.0\n", ""
            )
            result = install_pipx("csvkit")

        assert isinstance(result, InstallResult)
        assert result.method == METHOD_PIPX
        assert result.success is True
        assert result.returncode == 0
        assert "csvkit 1.3.0" in result.stdout
        assert result.elapsed_ms >= 0

    def test_command_has_no_sudo_and_uses_pipx_install(self):
        with patch("core.install.methods.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed(0)
            result = install_pipx("csvkit")

        assert "sudo" not in result.command
        assert "pipx" in result.command
        assert "install" in result.command
        assert "csvkit" in result.command

        called_args = mock_run.call_args[0][0]
        assert called_args == ["pipx", "install", "csvkit"]
        assert "sudo" not in called_args

    def test_non_zero_returncode_is_failure(self):
        with patch("core.install.methods.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed(
                1, "", "pipx ERROR: package not found"
            )
            result = install_pipx("not-a-real-package-name-xyz")

        assert result.success is False
        assert result.returncode == 1
        assert "pipx ERROR" in result.stderr

    def test_pipx_not_installed_collapses_to_command_not_found(self):
        """If pipx itself is missing from PATH, the typed-failure
        path in `_run` produces a clean InstallResult with
        returncode=-1 and a "command not found: pipx" stderr.
        Operator's recovery is install-pipx-outside-of-Concierge;
        the handler intentionally does NOT self-bootstrap pipx.
        """
        with patch("core.install.methods.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError(
                "No such file or directory: 'pipx'"
            )
            result = install_pipx("csvkit")

        assert result.success is False
        assert result.returncode == -1
        assert "command not found: pipx" in result.stderr

    def test_custom_timeout_passes_through_to_subprocess_run(self):
        with patch("core.install.methods.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed(0)
            install_pipx("csvkit", timeout_seconds=5.0)

        assert mock_run.call_args.kwargs["timeout"] == 5.0


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

    def test_timeout_collapses_to_returncode_minus_one(self, tmp_path):
        fake_venv = tmp_path / ".concierge" / "tools-venv"
        with patch("core.install.methods._ensure_concierge_venv") as mock_ensure, \
             patch("core.install.methods.subprocess.run") as mock_run:
            mock_ensure.return_value = fake_venv
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=[str(fake_venv / "bin" / "pip"), "install", "slow-package"],
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

    def test_os_error_collapses_to_returncode_minus_one(self, tmp_path):
        fake_venv = tmp_path / ".concierge" / "tools-venv"
        with patch("core.install.methods._ensure_concierge_venv") as mock_ensure, \
             patch("core.install.methods.subprocess.run") as mock_run:
            mock_ensure.return_value = fake_venv
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
            ("pipx", METHOD_PIPX),
            ("pipx install", METHOD_PIPX),
            ("pipx install csvkit", METHOD_PIPX),
            ("PIPX INSTALL", METHOD_PIPX),
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

    def test_pipx_takes_precedence_over_pip(self):
        """`"pipx"` must canonicalize to METHOD_PIPX, not METHOD_PIP_USER,
        even though `"pip" in "pipx"` is True. The pipx check must fire
        before the pip-user check in the normalizer — same shape as the
        existing npx-before-npm precedence guarantee.
        """
        assert normalize_install_method("pipx") == METHOD_PIPX
        assert normalize_install_method("pipx install csvkit") == METHOD_PIPX
        # Inverse: plain pip strings are unaffected by the pipx branch
        assert normalize_install_method("pip --user") == METHOD_PIP_USER
        assert normalize_install_method("pip install --user csvkit") == METHOD_PIP_USER


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

    def test_routes_pipx_to_install_pipx(self):
        with patch("core.install.service.install_pipx") as mock_pipx:
            mock_pipx.return_value = InstallResult(
                method=METHOD_PIPX,
                command="pipx install csvkit",
                success=True,
                returncode=0,
                stdout="",
                stderr="",
                elapsed_ms=100,
            )
            result = install_by_method("pipx", tool_name="csvkit")

        mock_pipx.assert_called_once_with("csvkit")
        assert result.method == METHOD_PIPX
        assert result.success is True

    def test_pipx_timeout_override_passes_through_to_installer(self):
        with patch("core.install.service.install_pipx") as mock_pipx:
            mock_pipx.return_value = InstallResult(
                method=METHOD_PIPX,
                command="",
                success=True,
                returncode=0,
                stdout="",
                stderr="",
                elapsed_ms=0,
            )
            install_by_method("pipx install", tool_name="csvkit", timeout_seconds=5.0)

        mock_pipx.assert_called_once_with("csvkit", timeout_seconds=5.0)

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
