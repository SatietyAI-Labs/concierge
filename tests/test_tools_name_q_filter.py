"""Wiring tests for the `name_q` filter on GET /tools — Day 10 Task 2.

Contracts under test:

1. **Substring match on `Tool.name`** — case-insensitive partial match.
2. **Substring match on `Tool.slug`** — operators searching for what
   they see on a card (which displays slug) match the slug field.
3. **Match name OR slug** — a row matches if either field has the
   substring; the OR is at the predicate level.
4. **Distinct results** — a row whose name AND slug both match
   appears exactly once.
5. **Empty / whitespace input → no filter applied** — returns full
   catalog (subject to other filters).
6. **Wildcard escape** — operator typing `_` or `%` matches the
   literal character, not the SQL LIKE wildcard.
7. **Combinable with existing filters** — `name_q` AND `tool_type`
   stack with AND semantics.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from core.app import create_app
from core.db.models import Tool
from core.db.session import get_db


def _client_with_session(db_session) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: (yield db_session)
    return TestClient(app)


class TestNameQFilter:

    def _seed(self, db_session) -> None:
        db_session.add_all(
            [
                Tool(slug="ripgrep", name="ripgrep", is_in_manifest=True),
                Tool(slug="rg-bin", name="ripgrep-3.0", is_in_manifest=True),
                Tool(slug="fd", name="fd-find", is_in_manifest=True),
                Tool(slug="jq", name="jq", is_in_manifest=True),
            ]
        )
        db_session.commit()

    def test_match_by_name_substring_case_insensitive(self, db_session):
        self._seed(db_session)
        client = _client_with_session(db_session)
        # uppercase query against lowercase name
        body = client.get("/tools", params={"name_q": "RIPGREP"}).json()
        slugs = sorted(t["slug"] for t in body["items"])
        # Both "ripgrep" (name match) and "rg-bin" (name="ripgrep-3.0"
        # name match) should hit; "fd" and "jq" should not.
        assert slugs == ["rg-bin", "ripgrep"]

    def test_match_by_slug_substring(self, db_session):
        """Slug-side match — operator searches for "rg-" sees the
        slug-side hit even when the name doesn't contain "rg-"."""
        self._seed(db_session)
        client = _client_with_session(db_session)
        body = client.get("/tools", params={"name_q": "rg-"}).json()
        slugs = [t["slug"] for t in body["items"]]
        assert "rg-bin" in slugs
        # "ripgrep" name contains "rg" but not "rg-"; should not match
        assert "ripgrep" not in slugs

    def test_match_name_or_slug_returns_either(self, db_session):
        self._seed(db_session)
        client = _client_with_session(db_session)
        # "fd" matches both fd's slug and fd-find's name
        body = client.get("/tools", params={"name_q": "fd"}).json()
        slugs = sorted(t["slug"] for t in body["items"])
        assert slugs == ["fd"]

    def test_distinct_when_both_name_and_slug_match(self, db_session):
        """A row whose name AND slug both contain the query appears
        exactly once."""
        db_session.add(Tool(slug="kitten", name="kitten", is_in_manifest=True))
        db_session.commit()
        client = _client_with_session(db_session)
        body = client.get("/tools", params={"name_q": "kit"}).json()
        items = body["items"]
        assert len(items) == 1
        assert items[0]["slug"] == "kitten"

    def test_empty_string_treated_as_no_filter(self, db_session):
        self._seed(db_session)
        client = _client_with_session(db_session)
        body = client.get("/tools", params={"name_q": ""}).json()
        # Should return all 4 seeded rows
        assert body["total"] == 4

    def test_whitespace_only_treated_as_no_filter(self, db_session):
        self._seed(db_session)
        client = _client_with_session(db_session)
        body = client.get("/tools", params={"name_q": "   "}).json()
        assert body["total"] == 4

    def test_wildcard_underscore_is_escaped(self, db_session):
        """Underscore in query matches literal underscore, not any
        single character."""
        db_session.add_all(
            [
                Tool(slug="abc_def", name="abc_def", is_in_manifest=True),
                Tool(slug="abcXdef", name="abcXdef", is_in_manifest=True),
            ]
        )
        db_session.commit()
        client = _client_with_session(db_session)
        body = client.get("/tools", params={"name_q": "abc_def"}).json()
        slugs = [t["slug"] for t in body["items"]]
        # Only abc_def (literal underscore); NOT abcXdef
        assert slugs == ["abc_def"]

    def test_wildcard_percent_is_escaped(self, db_session):
        """Percent in query matches literal `%`, not zero-or-more chars."""
        db_session.add_all(
            [
                Tool(slug="100pct", name="100% complete", is_in_manifest=True),
                Tool(slug="other", name="100 of these", is_in_manifest=True),
            ]
        )
        db_session.commit()
        client = _client_with_session(db_session)
        body = client.get("/tools", params={"name_q": "100%"}).json()
        slugs = [t["slug"] for t in body["items"]]
        # Only `100% complete` (literal `%`); NOT `100 of these`
        assert slugs == ["100pct"]

    def test_combinable_with_tool_type_filter(self, db_session):
        """name_q AND tool_type stack with AND semantics."""
        db_session.add_all(
            [
                Tool(
                    slug="pdf-cli", name="pdf-tool", tool_type="cli",
                    is_in_manifest=True,
                ),
                Tool(
                    slug="pdf-mcp", name="pdf-mcp-server", tool_type="mcp",
                    is_in_manifest=True,
                ),
                Tool(
                    slug="csv-cli", name="csv-tool", tool_type="cli",
                    is_in_manifest=True,
                ),
            ]
        )
        db_session.commit()
        client = _client_with_session(db_session)
        body = client.get(
            "/tools", params={"name_q": "pdf", "tool_type": "cli"}
        ).json()
        slugs = [t["slug"] for t in body["items"]]
        assert slugs == ["pdf-cli"]
