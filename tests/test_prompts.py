"""Smoke tests for `core.prompts.*` fragment constants.

Each fragment gets three layers of coverage:

1. **Import resolution** — module imports, constant name is exported.
2. **Signal-phrase assertions** — the constant contains four
   distinctive substrings drawn from top / middle / late-middle /
   bottom regions of the source body. These catch silent truncation
   in any region without asserting exact content (which would be
   brittle against whitespace drift).
3. **Drift detection** — the fragment body matches the corresponding
   section of the live source file under `_legacy/` byte-for-byte.
   Skips gracefully if the `_legacy/` symlink isn't accessible (the
   expected state on fresh clones without the private skill tree).
   On failure, surfaces sizes + a truncated unified diff so the drift
   is immediately diagnosable.
"""

import difflib
from pathlib import Path

import pytest

from core.prompts import (
    TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD,
    TOOL_DISCOVERY_PROTOCOL__FROM_TOOL_DISCOVERY_SKILL,
    TOOL_RECOMMENDATION_PROTOCOL__FROM_TOOL_RECOMMENDATION_MD,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
DIFF_TRUNCATE_CHARS = 3000


def _strip_yaml_frontmatter(text: str) -> str:
    """Remove a leading YAML `---`-delimited block and the blank line
    that follows it, if present. Returns the remainder verbatim.
    """
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    after_close = end + len("\n---")
    newline = text.find("\n", after_close)
    if newline == -1:
        return ""
    body = text[newline + 1 :]
    if body.startswith("\n"):
        body = body[1:]
    return body


def _assert_fragment_matches_source(
    fragment: str,
    source_relpath: str,
    test_nodeid: str,
) -> None:
    """Shared drift-check. Skips if source isn't accessible; otherwise
    asserts byte-for-byte equality and on failure raises with a
    unified diff and re-sync pointer.
    """
    source_path = REPO_ROOT / source_relpath
    if not source_path.exists():
        pytest.skip(
            f"{source_relpath} not accessible — drift check requires the "
            f"_legacy/ symlink tree"
        )
    source_body = _strip_yaml_frontmatter(source_path.read_text(encoding="utf-8"))
    if fragment == source_body:
        return

    diff = "".join(
        difflib.unified_diff(
            source_body.splitlines(keepends=True),
            fragment.splitlines(keepends=True),
            fromfile=f"source: {source_relpath}",
            tofile="fragment (constant value)",
            n=2,
        )
    )
    if len(diff) > DIFF_TRUNCATE_CHARS:
        diff = (
            diff[:DIFF_TRUNCATE_CHARS]
            + f"\n... (diff truncated at {DIFF_TRUNCATE_CHARS} chars; "
            "re-run locally with a longer limit if more detail is needed)"
        )

    message = (
        "Fragment has drifted from source.\n"
        "\n"
        f"Source body: {len(source_body)} chars, "
        f"{source_body.count(chr(10)) + 1} lines\n"
        f"Fragment:    {len(fragment)} chars, "
        f"{fragment.count(chr(10)) + 1} lines\n"
        "\n"
        f"{diff}"
        "\n"
        "Re-sync protocol: core/prompts/SKILL_FRAGMENT_SYNC_LOG.md "
        "§Drift model\n"
        f"Re-run after sync: pytest {test_nodeid}\n"
    )
    pytest.fail(message)


class TestToolAwarenessFragment:
    """X3 — tool-awareness.md → TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD"""

    def test_constant_is_nonempty_string(self):
        assert isinstance(TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD, str)
        assert len(TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD) > 0

    def test_signal_phrases_present(self):
        """Distinctive substrings sampled from four regions of the body.
        Catches silent truncation at top / middle / late-middle / bottom.
        """
        fragment = TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD
        assert "Tool-Awareness: Plan Before You Execute" in fragment  # top (H1)
        assert "Step 1: Task Decomposition" in fragment  # middle
        assert "Log to Wishlist" in fragment  # late-middle (Step 5)
        assert "Anti-Patterns (Do NOT Do These)" in fragment  # bottom H2

    def test_no_yaml_frontmatter_leaked_in(self):
        """The Anthropic skill-runtime metadata must not be in the prompt
        fragment — it's loader metadata, not prompt content.
        """
        fragment = TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD
        assert not fragment.startswith("---")
        assert "name: tool-awareness" not in fragment

    def test_matches_source_body_verbatim(self):
        """Drift check — the constant must equal the source body
        (frontmatter-stripped) byte-for-byte. On failure, surfaces a
        unified diff and the re-sync protocol pointer.
        """
        _assert_fragment_matches_source(
            fragment=TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD,
            source_relpath="_legacy/agent-skills/shared/tool-awareness.md",
            test_nodeid=(
                "tests/test_prompts.py::TestToolAwarenessFragment::"
                "test_matches_source_body_verbatim"
            ),
        )


class TestToolRecommendationFragment:
    """X4 — tool-recommendation.md → TOOL_RECOMMENDATION_PROTOCOL__FROM_TOOL_RECOMMENDATION_MD"""

    def test_constant_is_nonempty_string(self):
        assert isinstance(
            TOOL_RECOMMENDATION_PROTOCOL__FROM_TOOL_RECOMMENDATION_MD, str
        )
        assert len(TOOL_RECOMMENDATION_PROTOCOL__FROM_TOOL_RECOMMENDATION_MD) > 0

    def test_signal_phrases_present(self):
        """Distinctive substrings sampled from four regions of the body."""
        fragment = TOOL_RECOMMENDATION_PROTOCOL__FROM_TOOL_RECOMMENDATION_MD
        assert "Tool Recommendation: Notice, Evaluate, Propose" in fragment  # top H1
        assert "The calibration rule:" in fragment  # middle (when-does-not-fire)
        assert "Step 4: Write the Request" in fragment  # late-middle (process)
        assert "Anti-Patterns" in fragment  # bottom

    def test_no_yaml_frontmatter_leaked_in(self):
        fragment = TOOL_RECOMMENDATION_PROTOCOL__FROM_TOOL_RECOMMENDATION_MD
        assert not fragment.startswith("---")
        assert "name: tool-recommendation" not in fragment

    def test_matches_source_body_verbatim(self):
        _assert_fragment_matches_source(
            fragment=TOOL_RECOMMENDATION_PROTOCOL__FROM_TOOL_RECOMMENDATION_MD,
            source_relpath="_legacy/agent-skills/shared/tool-recommendation.md",
            test_nodeid=(
                "tests/test_prompts.py::TestToolRecommendationFragment::"
                "test_matches_source_body_verbatim"
            ),
        )


class TestToolDiscoveryFragment:
    """X6 — tool-discovery/SKILL.md → TOOL_DISCOVERY_PROTOCOL__FROM_TOOL_DISCOVERY_SKILL

    Demo-critical per classification §C.5.3 and Phase E Risk 1. The
    signal-table content is the headline example of prompt-fragment
    material. N8 smoke fixture assertion depends on this fragment
    functioning correctly inside Opus 4.7's system prompt.
    """

    def test_constant_is_nonempty_string(self):
        assert isinstance(TOOL_DISCOVERY_PROTOCOL__FROM_TOOL_DISCOVERY_SKILL, str)
        assert len(TOOL_DISCOVERY_PROTOCOL__FROM_TOOL_DISCOVERY_SKILL) > 0

    def test_signal_phrases_present(self):
        """Distinctive substrings sampled from four regions of the body.
        Late-middle phrase is inside the demo-critical signal table.
        """
        fragment = TOOL_DISCOVERY_PROTOCOL__FROM_TOOL_DISCOVERY_SKILL
        assert "Tool Discovery -- Finding What You Don't Know About" in fragment  # top
        assert "Search patterns by domain" in fragment  # middle
        assert "| GitHub stars | 1000+ | 100-999 | Under 100 |" in fragment  # demo-critical
        assert "This is how the catalog grows organically" in fragment  # bottom

    def test_no_yaml_frontmatter_leaked_in(self):
        fragment = TOOL_DISCOVERY_PROTOCOL__FROM_TOOL_DISCOVERY_SKILL
        assert not fragment.startswith("---")
        assert "name: tool-discovery" not in fragment

    def test_matches_source_body_verbatim(self):
        _assert_fragment_matches_source(
            fragment=TOOL_DISCOVERY_PROTOCOL__FROM_TOOL_DISCOVERY_SKILL,
            source_relpath="_legacy/openclaw-workspace/skills/tool-discovery/SKILL.md",
            test_nodeid=(
                "tests/test_prompts.py::TestToolDiscoveryFragment::"
                "test_matches_source_body_verbatim"
            ),
        )
