from core.db.models import Pack, Tool


def _seed(db):
    firefox = Pack(
        slug="firefox-devtools",
        name="Firefox DevTools",
        transport="stdio",
        status="active",
    )
    memory = Pack(
        slug="memory-mcp",
        name="Memory MCP",
        transport="stdio",
        status="active",
    )
    retired = Pack(
        slug="old-mcp",
        name="Old MCP",
        transport="http",
        status="retired",
    )
    db.add_all([firefox, memory, retired])
    db.flush()

    db.add_all(
        [
            Tool(slug="firefox-a", name="a", pack=firefox, is_in_manifest=True),
            Tool(slug="firefox-b", name="b", pack=firefox, is_in_manifest=True),
            Tool(slug="mem-a", name="ma", pack=memory, is_in_manifest=True),
        ]
    )
    db.commit()


def test_list_packs_empty(client_with_db):
    resp = client_with_db.get("/packs")
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0}


def test_list_packs_returns_all_with_tool_counts(client_with_db, db_session):
    _seed(db_session)
    resp = client_with_db.get("/packs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    by_slug = {p["slug"]: p for p in data["items"]}
    assert by_slug["firefox-devtools"]["tool_count"] == 2
    assert by_slug["memory-mcp"]["tool_count"] == 1
    assert by_slug["old-mcp"]["tool_count"] == 0


def test_list_packs_filter_by_status(client_with_db, db_session):
    _seed(db_session)
    resp = client_with_db.get("/packs?status=active")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert all(p["status"] == "active" for p in data["items"])


def test_list_packs_filter_by_transport(client_with_db, db_session):
    _seed(db_session)
    resp = client_with_db.get("/packs?transport=http")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["slug"] == "old-mcp"
