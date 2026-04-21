def test_health_endpoint(client):
    response = client.get("/health")
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
