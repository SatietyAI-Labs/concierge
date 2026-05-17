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
            lifecycle_state="loaded-on-boot",
        ),
        Tool(
            slug="csvkit",
            name="csvkit",
            category="data-processing",
            install_method="pip-user",
            is_in_manifest=True,
            lifecycle_state="discovered",  # dormant — in-manifest candidate
        ),
        Tool(
            slug="firefox-navigate",
            name="firefox_navigate",
            category="web",
            install_method="mcp-server",
            pack=firefox,
            is_in_manifest=True,
            lifecycle_state="loaded-on-boot",
        ),
        Tool(
            slug="memory-store",
            name="memory_store",
            category="ai-services",
            install_method="mcp-server",
            pack=memory,
            is_in_manifest=True,
            lifecycle_state="loaded-on-boot",
        ),
        Tool(
            slug="retired-noop",
            name="noop",
            is_in_manifest=False,
            lifecycle_state="retired",
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


def test_list_tools_filter_by_active(client_with_db, db_session):
    """`?active=true` → the loaded-on-boot set (replaced the retired
    `?is_active=` filter — DECISIONS D112)."""
    _seed(db_session)
    resp = client_with_db.get("/tools?active=true")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert {item["slug"] for item in data["items"]} == {
        "ripgrep",
        "firefox-navigate",
        "memory-store",
    }
    assert all(
        item["lifecycle_state"] == "loaded-on-boot" for item in data["items"]
    )


def test_list_tools_filter_by_active_false(client_with_db, db_session):
    """`?active=false` → every non-loaded-on-boot row."""
    _seed(db_session)
    resp = client_with_db.get("/tools?active=false")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert {item["slug"] for item in data["items"]} == {"csvkit", "retired-noop"}
    assert all(
        item["lifecycle_state"] != "loaded-on-boot" for item in data["items"]
    )


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
    """`?dormant=true` → in-manifest activation candidates: is_in_manifest
    AND lifecycle_state in (discovered, pending, pending-decision). The
    loaded-on-boot rows and the not-in-manifest `retired-noop` are
    excluded (DECISIONS D112, locked OD-1b)."""
    _seed(db_session)
    resp = client_with_db.get("/tools?dormant=true")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["slug"] == "csvkit"
    assert data["items"][0]["is_in_manifest"] is True
    assert data["items"][0]["lifecycle_state"] == "discovered"


def test_od1b_active_dormant_boundary(client_with_db, db_session):
    """OD-1b boundary guard (DECISIONS D112). Seeds one row in each of
    the seven lifecycle states, ALL is_in_manifest=True — so the
    manifest gate does NO exclusion work and the lifecycle predicate
    alone must classify every row.

    Load-bearing: `?dormant=true` (and /health `tools_dormant`) must
    EXCLUDE the retired and on-demand rows — settled states per D107,
    not activation candidates — even though they are is_in_manifest=True.
    That exclusion is the agent-facing misclassification OD-1b was
    decided to prevent; this test goes red if DORMANT_LIFECYCLE_STATES
    regresses to include retired / on-demand / used.
    """
    db_session.add_all([
        Tool(slug="boot-tool", name="boot", is_in_manifest=True,
             lifecycle_state="loaded-on-boot"),
        Tool(slug="od-tool", name="od", is_in_manifest=True,
             lifecycle_state="on-demand"),
        Tool(slug="ret-tool", name="ret", is_in_manifest=True,
             lifecycle_state="retired"),
        Tool(slug="used-tool", name="used", is_in_manifest=True,
             lifecycle_state="used"),
        Tool(slug="disc-tool", name="disc", is_in_manifest=True,
             lifecycle_state="discovered"),
        Tool(slug="pend-tool", name="pend", is_in_manifest=True,
             lifecycle_state="pending"),
        Tool(slug="pd-tool", name="pd", is_in_manifest=True,
             lifecycle_state="pending-decision"),
    ])
    db_session.commit()

    # /health catalog counts derive from lifecycle_state (D112).
    catalog = client_with_db.get("/health").json()["catalog"]
    assert catalog["tools"] == 7
    assert catalog["tools_active"] == 1    # loaded-on-boot only
    assert catalog["tools_dormant"] == 3   # discovered + pending + pending-decision

    # ?active=true → exactly the loaded-on-boot row.
    active = client_with_db.get("/tools?active=true").json()
    assert {i["slug"] for i in active["items"]} == {"boot-tool"}

    # ?dormant=true → the activation-candidate set, and ONLY that set.
    dormant = client_with_db.get("/tools?dormant=true").json()
    dormant_slugs = {i["slug"] for i in dormant["items"]}
    assert dormant_slugs == {"disc-tool", "pend-tool", "pd-tool"}
    # LOAD-BEARING: retired + on-demand + used are is_in_manifest=True
    # yet must NOT be classed dormant — settled / already-exercised
    # states are not activation candidates (D107). Regressing
    # DORMANT_LIFECYCLE_STATES turns these three assertions red.
    assert "ret-tool" not in dormant_slugs
    assert "od-tool" not in dormant_slugs
    assert "used-tool" not in dormant_slugs


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


def test_list_tools_filter_by_skill_tool_type_surfaces_path_and_ambient_loading(
    client_with_db, db_session
):
    _seed(db_session)
    db_session.add(
        Tool(
            slug="update-config",
            name="update-config",
            description="Configure settings.json",
            tool_type="skill",
            path="/mnt/skills/public/update-config/SKILL.md",
            ambient_loading=True,
            is_in_manifest=True,
        )
    )
    db_session.commit()

    resp = client_with_db.get("/tools", params={"tool_type": "skill"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["slug"] == "update-config"
    assert item["tool_type"] == "skill"
    assert item["path"] == "/mnt/skills/public/update-config/SKILL.md"
    assert item["ambient_loading"] is True
    assert item["lifecycle_state"] == "discovered"


def test_list_tools_non_skill_rows_report_null_path_and_ambient_loading(
    client_with_db, db_session
):
    _seed(db_session)
    resp = client_with_db.get("/tools")
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["path"] is None
        assert item["ambient_loading"] is None
