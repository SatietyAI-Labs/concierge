from pathlib import Path

from core.db.models import Request
from core.ingest import tool_requests as ti


def _parsed_to_request(parsed: ti.ParsedRequest) -> Request:
    return Request(
        filename=parsed.filename,
        status=parsed.status,
        folder=parsed.folder,
        tool_name=parsed.tool_name,
        tool_slug=parsed.tool_slug,
        category=parsed.category,
        confidence=parsed.confidence,
        is_discovered=parsed.is_discovered,
        raw_markdown=parsed.raw_markdown,
        parsed_data=parsed.sections,
    )


def test_export_produces_parseable_output(tmp_path: Path):
    content = (
        "status: approved\n\n"
        "# Tool Request: ripgrep (rg)\n\n"
        "## Request\n\n"
        "- **Task context:** big repo search\n"
        "- **Tool suggested:** ripgrep (rg)\n"
        "- **Category:** search\n\n"
        "## Recommendation\n\n"
        "- **Confidence:** high\n"
    )
    src = tmp_path / "2026-04-13-2028-ripgrep.md"
    src.write_text(content)
    parsed = ti.parse_request_file(src, "resolved")

    exported = ti.export_to_markdown(_parsed_to_request(parsed))
    dst = tmp_path / "exported.md"
    dst.write_text(exported)

    reparsed = ti.parse_request_file(dst, "resolved")
    assert reparsed.status == parsed.status
    assert reparsed.tool_name == parsed.tool_name
    assert reparsed.tool_slug == parsed.tool_slug
    assert reparsed.category == parsed.category
    assert reparsed.confidence == parsed.confidence
    assert reparsed.sections["request"]["task_context"] == "big repo search"
    assert reparsed.sections["request"]["category"] == "search"
    assert reparsed.sections["recommendation"]["confidence"] == "high"


def test_export_round_trip_real_legacy_file(tmp_path: Path):
    """Parse a real _legacy file, export it, re-parse — semantic content preserved."""
    from core.config import get_settings

    import pytest
    from pathlib import Path

    # Legacy-corpus test — reads the read-only `_legacy/tool-requests/`
    # symlink directly (not `settings.lifecycle_root`, which under the
    # operational-first pivot defaults to an isolated empty folder per
    # DECISIONS [2026-04-21 18:00]).
    legacy_root = (
        Path(__file__).resolve().parent.parent / "_legacy" / "tool-requests"
    )
    sample = legacy_root / "resolved" / "2026-04-13-1100-tree-for-codebase-nav.md"
    if not sample.exists():
        pytest.skip(f"real legacy fixture unavailable: {sample}")

    parsed = ti.parse_request_file(sample, "resolved")
    exported = ti.export_to_markdown(_parsed_to_request(parsed))

    dst = tmp_path / sample.name
    dst.write_text(exported)
    reparsed = ti.parse_request_file(dst, "resolved")

    assert reparsed.status == parsed.status
    assert reparsed.tool_name == parsed.tool_name
    for section in ("request", "recommendation", "approval", "install", "first_use", "outcome"):
        assert reparsed.sections.get(section) == parsed.sections.get(section), (
            f"section {section} diverged after round-trip"
        )


def test_export_includes_status_line_at_top():
    req = Request(
        filename="2026-04-13-1100-x.md",
        status="pending",
        folder="pending",
        tool_name="x",
        tool_slug="x",
        is_discovered=False,
        raw_markdown="",
        parsed_data={},
    )
    out = ti.export_to_markdown(req)
    assert out.startswith("status: pending\n")
    assert "# Tool Request: x" in out


def test_export_suppresses_discovery_only_fields_for_non_discovery_requests():
    req = Request(
        filename="2026-04-13-1100-x.md",
        status="pending",
        folder="pending",
        tool_name="x",
        tool_slug="x",
        is_discovered=False,
        raw_markdown="",
        parsed_data={"request": {"discovered": False}, "recommendation": {"confidence": "medium"}},
    )
    out = ti.export_to_markdown(req)
    assert "Source" not in out
    assert "Evidence" not in out


def test_export_includes_discovery_fields_when_present():
    req = Request(
        filename="2026-04-13-1100-x.md",
        status="pending",
        folder="pending",
        tool_name="x",
        tool_slug="x",
        is_discovered=True,
        raw_markdown="",
        parsed_data={
            "request": {"discovered": True},
            "recommendation": {
                "confidence": "medium",
                "source": "npm registry",
                "evidence": "12k downloads/week",
            },
        },
    )
    out = ti.export_to_markdown(req)
    assert "**Source:** npm registry" in out
    assert "**Evidence:** 12k downloads/week" in out
    assert "**Discovered:** true" in out
