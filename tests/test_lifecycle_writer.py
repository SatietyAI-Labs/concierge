"""Tests for core.lifecycle_store.writer — filename generation +
atomic writes + status-line update.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from core.lifecycle_store.schema import NewRequestDraft
from core.lifecycle_store.writer import (
    build_markdown,
    generate_filename,
    update_status_line,
    write_new_request,
)


class TestGenerateFilename:
    def test_shape(self):
        fn = generate_filename(
            tool_name="csvkit",
            when=datetime(2026, 4, 22, 9, 30),
        )
        assert fn == "2026-04-22-0930-csvkit.md"

    def test_slugifies_tool_name(self):
        fn = generate_filename(
            tool_name="Tool With Spaces!",
            when=datetime(2026, 4, 22, 9, 30),
        )
        assert fn == "2026-04-22-0930-tool-with-spaces.md"

    def test_uses_now_by_default(self):
        fn = generate_filename(tool_name="x")
        assert fn.startswith(datetime.now().strftime("%Y-%m-%d-"))


class TestBuildMarkdown:
    def test_minimal_draft(self):
        draft = NewRequestDraft(tool_name="csvkit")
        md = build_markdown(draft)
        assert md.startswith("status: pending\n")
        assert "# Tool Request: csvkit" in md

    def test_sections_rendered_when_populated(self):
        draft = NewRequestDraft(
            tool_name="csvkit",
            category="data",
            install_method="pip-user",
            task_context="Analyzing a CSV.",
            why_this_tool="Lightweight.",
            confidence="high",
            is_discovered=True,
        )
        md = build_markdown(draft)
        assert "## Request" in md
        assert "## Recommendation" in md
        assert "## Approval" in md  # stub present for cron to read
        assert "**Category:** data" in md
        assert "**Confidence:** high" in md
        assert "**Discovered:** true" in md

    def test_is_parseable_roundtrip(self, tmp_path):
        """build_markdown → parse_request_file must succeed so the
        DB row created after writing reflects what the cron reads.
        """
        from core.ingest.tool_requests import parse_request_file

        draft = NewRequestDraft(
            tool_name="csvkit",
            category="data",
            install_method="pip-user",
            task_context="x",
            why_this_tool="y",
            confidence="medium",
        )
        path = tmp_path / "2026-04-22-0900-csvkit.md"
        path.write_text(build_markdown(draft))
        parsed = parse_request_file(path, "pending")
        assert parsed.status == "pending"
        assert parsed.tool_name == "csvkit"
        assert parsed.category == "data"
        assert parsed.confidence == "medium"


class TestAtomicWrite:
    def test_write_new_request_creates_pending_file(self, tmp_path):
        root = tmp_path
        draft = NewRequestDraft(tool_name="csvkit", category="data")
        path = write_new_request(
            lifecycle_root=root,
            draft=draft,
            filename="2026-04-22-0930-csvkit.md",
        )
        assert path == root / "pending" / "2026-04-22-0930-csvkit.md"
        assert path.exists()
        content = path.read_text()
        assert content.startswith("status: pending\n")

    def test_refuses_to_overwrite_existing(self, tmp_path):
        root = tmp_path
        (root / "pending").mkdir()
        target = root / "pending" / "existing.md"
        target.write_text("status: pending\n\n# Tool Request: existing\n")
        with pytest.raises(FileExistsError):
            write_new_request(
                lifecycle_root=root,
                draft=NewRequestDraft(tool_name="existing"),
                filename="existing.md",
            )

    def test_no_partial_file_visible_on_write_failure(self, tmp_path, monkeypatch):
        """Simulate an `os.replace` failure and assert no `.tmp`
        leftover is visible under the canonical filename.
        """
        import core.lifecycle_store.writer as writer_mod

        root = tmp_path
        (root / "pending").mkdir()

        original_replace = writer_mod.os.replace

        def boom(src, dst):
            # Remove the tempfile and raise, simulating the mid-
            # rename failure mode.
            try:
                writer_mod.os.unlink(src)
            except Exception:
                pass
            raise OSError("simulated replace failure")

        monkeypatch.setattr(writer_mod.os, "replace", boom)

        with pytest.raises(OSError, match="simulated"):
            write_new_request(
                lifecycle_root=root,
                draft=NewRequestDraft(tool_name="x"),
                filename="2026-04-22-0930-x.md",
            )

        # Target path must not have been created.
        assert not (root / "pending" / "2026-04-22-0930-x.md").exists()
        # No .tmp leftover in the directory (we unlinked in the
        # boom fake above).
        leftovers = list((root / "pending").glob("*.tmp"))
        assert leftovers == []


class TestUpdateStatusLine:
    def _write(self, path: Path, status: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"status: {status}\n\n# Tool Request: x\n\n## Request\n\n- **Category:** data\n"
        )

    def test_status_line_replaced(self, tmp_path):
        path = tmp_path / "pending" / "x.md"
        self._write(path, "pending")
        update_status_line(path=path, new_status="approved")
        content = path.read_text()
        assert content.startswith("status: approved\n")
        # Body preserved.
        assert "# Tool Request: x" in content
        assert "**Category:** data" in content

    def test_body_byte_preserved_except_status(self, tmp_path):
        path = tmp_path / "pending" / "x.md"
        self._write(path, "pending")
        before = path.read_text()
        update_status_line(path=path, new_status="approved")
        after = path.read_text()
        # Only the first line differs.
        before_lines = before.splitlines()
        after_lines = after.splitlines()
        assert after_lines[0] == "status: approved"
        assert before_lines[1:] == after_lines[1:]

    def test_missing_status_line_raises(self, tmp_path):
        path = tmp_path / "pending" / "bad.md"
        path.parent.mkdir()
        path.write_text("# no status line here\n")
        with pytest.raises(ValueError, match="no status line"):
            update_status_line(path=path, new_status="approved")
