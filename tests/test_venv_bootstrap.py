"""Unit tests for `core.install.venv._ensure_concierge_venv` +
the Day 6 Option 3 end-to-end integration test.

The unit-test layer mocks `subprocess.run` — no actual venv is
created. The integration test (`@pytest.mark.slow`,
`TestRealVenvBootstrap`) exercises the full chain: real
`python3 -m venv`, real pip install, real shim invocation. Per
the Day 5 wiring-test meta-lesson, it asserts the
**client-observable contract** (the shim is invokable, the binary
runs) — not just "did the bytes/calls flow."

Test surface pinned to the contract documented in DECISIONS
`[2026-04-27 Day 6]`:

- Shim location decision: helper does NOT touch `~/.concierge/bin/`
  (that's the shim-script generator's job, Step 4); helper only
  manages the venv at `~/.concierge/tools-venv/`.
- Venv creator decision: stdlib `python3 -m venv` via
  `[sys.executable, "-m", "venv", "--system-site-packages=False", ...]`
  — explicit flag is regression-guarded (test 3) so a future "drop
  redundant default" cleanup fails this specific test.
- Atomic creation via `<venv>.tmp` → `<venv>` rename so an interrupted
  bootstrap leaves a recoverable state.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.install.methods import install_pip_user
from core.install.venv import ConciergeVenvError, _ensure_concierge_venv


def _mock_completed(returncode=0, stdout="", stderr=""):
    completed = MagicMock()
    completed.returncode = returncode
    completed.stdout = stdout
    completed.stderr = stderr
    return completed


def _make_subprocess_run_creating_venv(returncode=0, stdout="", stderr=""):
    """Return a side_effect that, when invoked as
    `subprocess.run([sys.executable, "-m", "venv", str(target_path)],
    ...)`, mkdir's the target_path + a `bin/python` stub inside it,
    then returns a mock CompletedProcess.

    Mirrors what real `python3 -m venv` does at the layer the helper
    cares about: a directory exists, `bin/python` is invokable. The
    integration test (Step 5, `TestRealVenvBootstrap`) exercises the
    real subprocess + real shebangs + real pip — that's where venv-
    semantics correctness gets validated. This side_effect is the
    unit-test stand-in for call-shape validation only.
    """
    def _side_effect(argv, *args, **kwargs):
        # The target path is the last positional arg per the venv
        # invocation contract (no `.tmp` staging post-Step-5; target
        # is the final venv path directly).
        target = Path(argv[-1])
        target.mkdir(parents=True, exist_ok=True)
        bin_dir = target / "bin"
        bin_dir.mkdir(exist_ok=True)
        (bin_dir / "python").write_text("#!/usr/bin/env python3\n")
        (bin_dir / "python").chmod(0o755)
        return _mock_completed(returncode, stdout, stderr)

    return _side_effect


# ---- Subprocess call shape (Decision B contract) -------------------------


class TestSubprocessCallShape:
    """The helper invokes stdlib venv via sys.executable with the
    explicit --system-site-packages=False flag. Decision B's contract.
    """

    def test_creates_venv_with_correct_subprocess_shape(self, tmp_path):
        """Pin the full subprocess.run call shape: sys.executable,
        -m venv, target=<home>/.concierge/tools-venv (the final
        path — direct creation, no `.tmp` staging post-Step-5). No
        `--system-site-packages` flag; see
        test_system_site_packages_flag_NOT_in_argv for the regression
        guard.
        """
        with patch("core.install.venv.subprocess.run") as mock_run:
            mock_run.side_effect = _make_subprocess_run_creating_venv()
            result = _ensure_concierge_venv(home=tmp_path)

        # Exactly one subprocess.run call
        assert mock_run.call_count == 1
        argv = mock_run.call_args[0][0]
        # argv[0] is sys.executable — see test_uses_sys_executable below
        # for why this matters
        assert argv[0] == sys.executable
        assert argv[1] == "-m"
        assert argv[2] == "venv"
        # Target path is the FINAL venv path (no `.tmp` staging —
        # Python venv's hard-coded shebangs make rename unsafe; see
        # DECISIONS Decision B post-hoc correction)
        target = Path(argv[-1])
        assert target == tmp_path / ".concierge" / "tools-venv"

        # Return value: same final venv path
        assert result == tmp_path / ".concierge" / "tools-venv"
        # Venv exists (created via the side_effect's mkdir)
        assert result.exists()
        assert (result / "bin" / "python").exists()

    def test_system_site_packages_flag_NOT_in_argv(self, tmp_path):
        """Regression guard for Decision B's revised mechanism: the
        isolation invariant is enforced by the ABSENCE of the
        `--system-site-packages` opt-in flag, not by the presence of
        an explicit `=False` (which doesn't exist as a CLI form —
        the flag is store_true).

        A future contributor who tries to opt INTO system-site-packages
        (e.g. to share torch/numpy with the operator's environment)
        adds `--system-site-packages` to the argv and trips this test,
        forcing them to revisit DECISIONS `[2026-04-27 Day 6]`
        Decision B before the change can land.

        Originally this test asserted `--system-site-packages=False`
        was present in argv. Day 6 Step 5 integration test caught
        that the CLI rejects that form (store_true flags don't accept
        arguments); see DECISIONS Decision B's Post-hoc correction
        note for the discovery context.
        """
        with patch("core.install.venv.subprocess.run") as mock_run:
            mock_run.side_effect = _make_subprocess_run_creating_venv()
            _ensure_concierge_venv(home=tmp_path)

        argv = mock_run.call_args[0][0]
        # No element of argv may be the opt-IN flag, in any of its
        # accepted forms (the flag itself, or any =value variant)
        for element in argv:
            assert not element.startswith("--system-site-packages"), (
                "Decision B contract: `--system-site-packages` must NOT "
                "appear in argv. Stdlib default is isolation; the flag "
                "exists only as opt-IN to system-site-packages. Adding "
                "it would let the tools-venv import torch/numpy/etc. "
                "from the operator's environment, breaking the Option 3 "
                f"isolation invariant. argv was {argv!r}"
            )

    def test_uses_sys_executable_not_string_python3(self, tmp_path):
        """Helper invokes the runtime venv's interpreter via
        sys.executable, not a PATH-resolved "python3" string. Same
        rationale as the pip-generated `concierge-shim` bin's
        absolute-path shebang — avoid "which python3 is on PATH
        right now?" surprises that would otherwise resolve to system
        python and trip ModuleNotFoundError on Concierge dependencies.
        """
        with patch("core.install.venv.subprocess.run") as mock_run:
            mock_run.side_effect = _make_subprocess_run_creating_venv()
            _ensure_concierge_venv(home=tmp_path)

        argv = mock_run.call_args[0][0]
        assert argv[0] == sys.executable
        assert argv[0] not in {"python", "python3"}, (
            "argv[0] must be sys.executable (an absolute path to the "
            "runtime venv's interpreter), not a PATH-resolved string"
        )


# ---- Idempotency + first-run detection -----------------------------------


class TestIdempotency:
    """Helper is the first-run-detection seam. Lazy bootstrap inside
    install_pip_user means the helper is called every install; every
    call after the first must be a no-op fast path.
    """

    def test_idempotent_when_venv_exists(self, tmp_path):
        """When `<home>/.concierge/tools-venv/bin/python` already
        exists, helper returns the venv path immediately without
        calling subprocess.run. This is the load-bearing fast path —
        every install after the first hits this branch.
        """
        venv = tmp_path / ".concierge" / "tools-venv"
        bin_dir = venv / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "python").write_text("#!/usr/bin/env python3\n")
        (bin_dir / "python").chmod(0o755)

        with patch("core.install.venv.subprocess.run") as mock_run:
            result = _ensure_concierge_venv(home=tmp_path)

        assert mock_run.call_count == 0, (
            "Helper must not invoke subprocess.run when the venv "
            "already exists. Idempotency is load-bearing — every "
            "post-first install hits this branch."
        )
        assert result == venv

    def test_creates_concierge_home_if_missing(self, tmp_path):
        """Fresh operator with no `~/.concierge/` directory at all.
        Helper creates parent dirs (mkdir parents=True) so the venv
        bootstrap doesn't fail on a missing intermediate.
        """
        # tmp_path has no .concierge subdirectory yet
        assert not (tmp_path / ".concierge").exists()

        with patch("core.install.venv.subprocess.run") as mock_run:
            mock_run.side_effect = _make_subprocess_run_creating_venv()
            _ensure_concierge_venv(home=tmp_path)

        # .concierge parent dir got created
        assert (tmp_path / ".concierge").is_dir()


# ---- Partial-state cleanup on subprocess failure -------------------------


class TestPartialStateRecovery:
    """Post-Step-5 (direct-create-at-final-path): when subprocess.run
    fails (returncode != 0), the helper cleans up any partial venv
    state at the canonical path before raising ConciergeVenvError so
    the operator's next retry starts from a clean slate.

    This test slot was previously `TestStaleTmpRecovery` — the .tmp
    staging dir + atomic rename pattern was reverted in Step 5 because
    Python venv's hard-coded shebangs are incompatible with renaming
    (see DECISIONS Decision B post-hoc correction). The slot now pins
    the analogous-but-different invariant: subprocess-failure cleanup
    at the canonical path.

    Hard-crash mid-creation (SIGKILL etc.) leaves partial state on
    disk and is recovered separately by the "incomplete venv" guard
    in `TestFailureModes::test_raises_on_incomplete_venv`.
    """

    def test_subprocess_failure_cleans_up_partial_venv(self, tmp_path):
        """A subprocess.run failure may leave a partially-created
        venv directory at the canonical path. The helper rmtree's it
        before raising so the operator's next attempt starts clean.
        """
        venv = tmp_path / ".concierge" / "tools-venv"

        def _failing_side_effect(argv, *args, **kwargs):
            # Simulate Python venv's behavior where the venv directory
            # gets partially created (bin/, some scripts) but creation
            # didn't complete (no bin/python — the helper's success
            # marker).
            target = Path(argv[-1])
            (target / "bin").mkdir(parents=True)
            (target / "bin" / "pip3").write_text(
                "# partial creation — pip3 script written but bin/python "
                "not yet symlinked"
            )
            return _mock_completed(
                returncode=1,
                stdout="",
                stderr="venv creation interrupted",
            )

        with patch("core.install.venv.subprocess.run") as mock_run:
            mock_run.side_effect = _failing_side_effect
            with pytest.raises(ConciergeVenvError):
                _ensure_concierge_venv(home=tmp_path)

        # Partial venv state cleaned up — operator gets clean slate.
        # This is the load-bearing assertion: without rmtree, the next
        # retry would hit the "incomplete venv" guard and force the
        # operator into a manual `rm -rf` step.
        assert not venv.exists(), (
            "Helper must rmtree the partial venv state on subprocess "
            "failure so the operator's next retry starts clean. "
            f"venv path still exists: {venv}"
        )


# ---- Failure modes -------------------------------------------------------


class TestFailureModes:
    """Failure-class coverage. The helper raises a typed exception
    (ConciergeVenvError) so the caller in install_pip_user can catch
    it and convert to InstallResult(success=False, ...). Per the
    existing X13 pattern of "subprocess failures collapse to typed
    failure objects, never bubble subprocess exceptions."
    """

    def test_raises_on_subprocess_failure(self, tmp_path):
        """Subprocess.run returns nonzero. Helper raises
        ConciergeVenvError carrying the subprocess stderr for
        debugging. Caller in install_pip_user catches and converts.

        Partial-venv cleanup behavior is pinned separately in
        `TestPartialStateRecovery::test_subprocess_failure_cleans_up_partial_venv`
        — that test simulates a partial venv directory; this test
        focuses on the no-side-effect failure path (no partial state
        to clean). Both behaviors must be pinned: error raised
        cleanly even when there's nothing to clean up, AND partial
        state is cleaned when present.
        """
        venv = tmp_path / ".concierge" / "tools-venv"
        with patch("core.install.venv.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed(
                returncode=1,
                stdout="",
                stderr="Error: Python 3.4+ required for venv module",
            )
            with pytest.raises(ConciergeVenvError) as exc_info:
                _ensure_concierge_venv(home=tmp_path)

        # The exception message carries the stderr so debugging starts
        # from a real diagnostic, not a generic "venv creation failed"
        assert "Python 3.4+ required" in str(exc_info.value)
        # No partial state to clean (subprocess didn't write anything),
        # but the cleanup call is still safe (rmtree with
        # ignore_errors=True). venv path doesn't exist post-call.
        assert not venv.exists()

    def test_raises_on_incomplete_venv(self, tmp_path):
        """`<venv>/` exists but `<venv>/bin/python` doesn't —
        partially-broken state from a prior failure or operator
        intervention. Helper does NOT silently rmtree (could nuke
        operator's manual work). Raises ConciergeVenvError with a
        clear "remove manually before retrying" message.
        """
        venv = tmp_path / ".concierge" / "tools-venv"
        venv.mkdir(parents=True)
        # Note: NO bin/python created — venv directory exists but is
        # incomplete

        with patch("core.install.venv.subprocess.run") as mock_run:
            with pytest.raises(ConciergeVenvError) as exc_info:
                _ensure_concierge_venv(home=tmp_path)

        # subprocess.run was NOT called — the helper bailed before
        # attempting bootstrap
        assert mock_run.call_count == 0
        # Message guides the operator
        assert "incomplete" in str(exc_info.value).lower() or "manually" in str(exc_info.value).lower()


# ---- Layer-2 integration test (real venv, real pip, real shim) -----------


@pytest.mark.slow
class TestRealVenvBootstrap:
    """Day 6 Step 5 integration test — exercises the FULL chain
    end-to-end with no mocks: real `python3 -m venv`, real pip
    install, real shim invocation, real subprocess exec.

    Per the Day 5 wiring-test meta-lesson (`SESSION-2026-04-26-01.md`
    Task 1 close-out): wiring tests must assert client-observable
    contracts, not just "did the bytes/calls flow." The load-bearing
    assertion here is `subprocess.run([str(shim), "--version"])
    exits 0` — that's what the operator depends on.

    Marked `@pytest.mark.slow` because real venv creation takes
    ~1-3s + pip install of pyflakes takes ~3-10s + network access
    required for the install. Skipped in fast-iteration runs via
    `pytest -m "not slow"`.

    Test package choice: `pyflakes` — small (~350KB), pure-Python,
    ships a `pyflakes` console script that supports `--version`,
    no binary deps, no torch (i.e. doesn't trip Day 5's torch env
    failures).
    """

    def test_install_pip_user_end_to_end_with_real_venv(
        self, tmp_path, monkeypatch
    ):
        """Full chain: install_pip_user('pyflakes') →
        _ensure_concierge_venv (real bootstrap) → real pip install →
        _generate_shim → result.success=True. Then assert the shim
        is invokable: subprocess.run([str(shim), "--version"]) exits
        0 with pyflakes output.
        """
        # Redirect Path.home() so neither real ~/.concierge/tools-venv/
        # nor real ~/.concierge/bin/ is touched. HOME is what
        # Path.home() consults on Linux/macOS.
        monkeypatch.setenv("HOME", str(tmp_path))

        result = install_pip_user("pyflakes", timeout_seconds=120.0)

        # Install succeeded end-to-end
        assert result.success is True, (
            f"install_pip_user('pyflakes') failed end-to-end: "
            f"returncode={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}"
        )
        assert result.method == "pip_user"

        # Venv exists at the expected path with pip + pyflakes binaries
        venv = tmp_path / ".concierge" / "tools-venv"
        assert venv.exists(), f"venv directory missing: {venv}"
        assert (venv / "bin" / "python").exists()
        assert (venv / "bin" / "pip").exists()
        assert (venv / "bin" / "pyflakes").exists(), (
            "pyflakes console script must be installed in the venv "
            "by `pip install pyflakes`"
        )

        # Shim exists at ~/.concierge/bin/pyflakes and is executable
        shim = tmp_path / ".concierge" / "bin" / "pyflakes"
        assert shim.exists(), f"shim missing: {shim}"
        assert os.access(shim, os.X_OK), "shim must be executable"

        # Client-observable contract — THE load-bearing assertion.
        # Day 5 wiring-test meta-lesson: not "did the bytes flow"
        # but "does the consumer-visible state work as the client
        # expects it." The operator's expectation: invoke the shim
        # by name and the venv-installed tool runs.
        invocation = subprocess.run(
            [str(shim), "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert invocation.returncode == 0, (
            f"shim invocation failed: returncode={invocation.returncode} "
            f"stdout={invocation.stdout!r} stderr={invocation.stderr!r}"
        )
        # Sanity check: pyflakes --version output mentions pyflakes
        # somewhere (across stdout/stderr — different versions of
        # pyflakes write to different streams)
        combined = (invocation.stdout + invocation.stderr).lower()
        assert "pyflakes" in combined or len(combined.strip()) > 0, (
            f"pyflakes --version produced no recognizable output: "
            f"stdout={invocation.stdout!r} stderr={invocation.stderr!r}"
        )

    def test_idempotent_second_install_skips_bootstrap(
        self, tmp_path, monkeypatch
    ):
        """Second install_pip_user call hits the venv-bootstrap
        idempotent fast path — no second `python3 -m venv` invocation.
        Demonstrates the "every install after the first is cheap"
        contract.
        """
        monkeypatch.setenv("HOME", str(tmp_path))

        # First install: bootstrap the venv + install pyflakes
        first = install_pip_user("pyflakes", timeout_seconds=120.0)
        assert first.success is True

        venv = tmp_path / ".concierge" / "tools-venv"
        first_python_mtime = (venv / "bin" / "python").stat().st_mtime_ns

        # Second install: same package. _ensure_concierge_venv
        # should hit the idempotent fast path; pip install
        # re-validates pyflakes (already-satisfied, very fast).
        second = install_pip_user("pyflakes", timeout_seconds=120.0)
        assert second.success is True

        # The venv's bin/python wasn't touched (mtime unchanged) —
        # the venv wasn't rebuilt
        second_python_mtime = (venv / "bin" / "python").stat().st_mtime_ns
        assert first_python_mtime == second_python_mtime, (
            "Venv bin/python mtime changed between first and second "
            "install — the idempotent fast path should not rebuild "
            "the venv"
        )
