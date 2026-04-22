"""Lint test — no `print(` calls anywhere under `adapters/claude_code/`.

The operational invariant: **stdout is reserved for JSON-RPC**.
A single `print(...)` call contaminates the protocol stream and
kills the Claude Code MCP client. This test is the static check;
`test_shim_e2e.py::TestStdoutPurity` is the dynamic check over a
range of runtime scenarios. Both fire — we want belt + suspenders
on this invariant.

Scope: the `adapters/claude_code/` package only. Other packages
(`core/`, `ui/`) are free to `print(` because they don't drive
stdio framing.
"""
from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = (
    Path(__file__).resolve().parent.parent / "adapters" / "claude_code"
)


def test_no_print_calls_in_shim_package():
    """AST-based scan. Finds actual `print(...)` call expressions,
    ignoring mentions inside docstrings, comments, or other string
    literals. Any real `print()` call-site fails the test and
    forces a code-review pause — that's the right behavior for a
    stdout-purity invariant.
    """
    import ast

    offenders: list[tuple[Path, int, str]] = []
    for py_file in sorted(PACKAGE_ROOT.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError as exc:
            offenders.append((py_file, exc.lineno or 0, f"SyntaxError: {exc}"))
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "print":
                    offenders.append(
                        (py_file, node.lineno, ast.get_source_segment(source, node) or "")
                    )

    assert not offenders, (
        "Found print(...) call-sites under adapters/claude_code/; stdout is "
        "reserved for JSON-RPC framing — use logging instead. "
        f"Offenders: {offenders}"
    )


def test_no_sys_stdout_attribute_access_outside_shim_emit():
    """Secondary check via AST: only `shim._emit` may reference
    `sys.stdout` as an attribute. Any `sys.stdout.*` read or write
    outside that function is a suspect leak path.
    """
    import ast

    offenders: list[tuple[Path, int, str]] = []
    for py_file in sorted(PACKAGE_ROOT.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))
        # Walk functions; track current function name so we can
        # whitelist `_emit` in shim.py.
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if (
                    isinstance(node.value, ast.Attribute)
                    and isinstance(node.value.value, ast.Name)
                    and node.value.value.id == "sys"
                    and node.value.attr == "stdout"
                ):
                    # e.g. `sys.stdout.write` — a dotted-attr.
                    lineno = node.lineno
                    src = ast.get_source_segment(source, node) or ""
                    # Whitelist: `_emit`'s `sys.stdout` as the
                    # fallback when no `out` argument was passed
                    # (`target = out if out is not None else sys.stdout`).
                    if py_file.name == "shim.py" and "else sys.stdout" in (
                        source.splitlines()[lineno - 1]
                        if 1 <= lineno <= len(source.splitlines())
                        else ""
                    ):
                        continue
                    offenders.append((py_file, lineno, src))
    assert not offenders, (
        f"Found sys.stdout.* attribute access outside the permitted "
        f"shim._emit fallback: {offenders}"
    )
