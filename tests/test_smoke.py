def test_health_endpoint(client_with_db):
    # D111 — routed through `client_with_db` (overridden `get_db` → in-memory
    # session) rather than a bare `TestClient(create_app())`, so this smoke
    # check never reads the production catalog DB via the real engine.
    response = client_with_db.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["env"] == "dev"
    assert data["version"] == "0.1.0"


def test_app_factory_independent_instances():
    from core.app import create_app

    app_a = create_app()
    app_b = create_app()
    assert app_a is not app_b
    assert app_a.title == app_b.title == "Concierge"


def test_settings_loads():
    from core.config import get_settings

    settings = get_settings()
    assert isinstance(settings.env, str) and settings.env
    assert settings.log_level.upper() in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
