from datetime import datetime

from core.db.models import Pack, Tool


def _seed(db):
    firefox = Pack(slug="firefox-devtools", name="Firefox DevTools", transport="stdio")
    memory = Pack(slug="memory-mcp", name="Memory MCP", transport="stdio")
    db.add_all([firefox, memory])
    db.flush()

    tools = [
        Tool(
            slug="ripgrep",
            name="ripgrep",
            category="search",
            install_method="apt",
            is_in_manifest=True,
            is_active=True,
        ),
        Tool(
            slug="csvkit",
            name="csvkit",
            category="data-processing",
            install_method="pip-user",
            is_in_manifest=True,
            is_active=False,
        ),
        Tool(
            slug="firefox-navigate",
            name="firefox_navigate",
            category="web",
            install_method="mcp-server",
            pack=firefox,
            is_in_manifest=True,
            is_active=True,
        ),
        Tool(
            slug="memory-store",
            name="memory_store",
            category="ai-services",
            install_method="mcp-server",
            pack=memory,
            is_in_manifest=True,
            is_active=True,
        ),
        Tool(
            slug="retired-noop",
            name="noop",
            is_in_manifest=False,
            is_active=False,
        ),
    ]
    db.add_all(tools)
    db.commit()


def test_list_tools_empty(client_with_db):
    resp = client_with_db.get("/tools")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"items": [], "total": 0}


def test_list_tools_returns_all(client_with_db, db_session):
    _seed(db_session)
    resp = client_with_db.get("/tools")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 5
    slugs = {item["slug"] for item in data["items"]}
    assert slugs == {"ripgrep", "csvkit", "firefox-navigate", "memory-store", "retired-noop"}


def test_list_tools_filter_by_is_active(client_with_db, db_session):
    _seed(db_session)
    resp = client_with_db.get("/tools?is_active=true")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert all(item["is_active"] for item in data["items"])


def test_list_tools_filter_by_category(client_with_db, db_session):
    _seed(db_session)
    resp = client_with_db.get("/tools?category=search")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["slug"] == "ripgrep"


def test_list_tools_filter_by_pack_slug(client_with_db, db_session):
    _seed(db_session)
    resp = client_with_db.get("/tools?pack_slug=memory-mcp")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["slug"] == "memory-store"
    assert item["pack_slug"] == "memory-mcp"
    assert item["pack_name"] == "Memory MCP"


def test_list_tools_dormant_filter(client_with_db, db_session):
    _seed(db_session)
    resp = client_with_db.get("/tools?dormant=true")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["slug"] == "csvkit"
    assert data["items"][0]["is_in_manifest"] is True
    assert data["items"][0]["is_active"] is False


def test_list_tools_by_slug(client_with_db, db_session):
    _seed(db_session)
    resp = client_with_db.get("/tools?slug=ripgrep")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["slug"] == "ripgrep"


def test_list_tools_pagination(client_with_db, db_session):
    _seed(db_session)
    resp = client_with_db.get("/tools?limit=2&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2


def test_get_tool_by_id(client_with_db, db_session):
    _seed(db_session)
    first = db_session.query(Tool).filter_by(slug="ripgrep").one()
    resp = client_with_db.get(f"/tools/{first.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["slug"] == "ripgrep"
    assert data["category"] == "search"
    assert data["pack_id"] is None


def test_get_tool_by_id_with_pack(client_with_db, db_session):
    _seed(db_session)
    row = db_session.query(Tool).filter_by(slug="memory-store").one()
    resp = client_with_db.get(f"/tools/{row.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["pack_slug"] == "memory-mcp"
    assert data["pack_name"] == "Memory MCP"


def test_get_tool_by_id_404(client_with_db):
    resp = client_with_db.get("/tools/99999")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "tool not found"}
