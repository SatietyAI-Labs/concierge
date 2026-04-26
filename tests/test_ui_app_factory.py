"""Wiring tests for the Day 10 UI app factory + composition pattern.

Three contracts under test:

1. **`ui.create_app()` produces a working dashboard app.** GET / renders
   the placeholder index template with the expected marker; the
   StaticFiles mount at `/static` resolves vendored assets.

2. **`core.create_app()` stays UI-free.** Headless deployments use the
   core factory directly; GET / returns 404 because the UI router is
   not included.

3. **`ui.app` is factory-only.** The module exposes the `create_app()`
   factory but does NOT expose a module-level `app` attribute. Locks
   the contract against accidental retrofit (matches `core.app`
   factory-only pattern applied in the Day 10 mid-Task-0 refactor).
"""
from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

import ui.app
from core.app import create_app as create_core_app
from ui.app import create_app as create_ui_app


# ---- Contract 1: ui.create_app() works end-to-end ------------------


class TestUiAppFactory:
    def test_get_index_returns_200(self) -> None:
        client = TestClient(create_ui_app())
        resp = client.get("/")
        assert resp.status_code == 200

    def test_get_index_renders_placeholder_marker(self) -> None:
        client = TestClient(create_ui_app())
        resp = client.get("/")
        # Marker from ui/templates/index.html — Task 0 placeholder;
        # Task 4 replaces the body but keeps the "Concierge" title.
        assert "Concierge" in resp.text
        assert "placeholder-marker" in resp.text

    def test_static_vendor_htmx_resolves(self) -> None:
        client = TestClient(create_ui_app())
        resp = client.get("/static/vendor/htmx.min.js")
        assert resp.status_code == 200
        # Spot-check the file actually came from the vendored bundle:
        # HTMX's banner string is stable across patch releases.
        assert "htmx" in resp.text.lower()

    def test_static_vendor_pico_resolves(self) -> None:
        client = TestClient(create_ui_app())
        resp = client.get("/static/vendor/pico.min.css")
        assert resp.status_code == 200
        # Pico is a CSS file; minified-but-valid CSS contains braces.
        assert "{" in resp.text


# ---- Contract 2: core.create_app() stays UI-free -------------------


class TestCoreAppHeadlessSurface:
    def test_get_index_returns_404_on_core_factory(self) -> None:
        """Headless deployments instantiate `core.create_app()` directly.
        The dashboard route lives only on the ui-augmented app."""
        client = TestClient(create_core_app())
        resp = client.get("/")
        assert resp.status_code == 404

    def test_static_mount_absent_on_core_factory(self) -> None:
        """The /static mount is added by ui.app.create_app(), not by
        core.app.create_app(). Confirms the composition boundary."""
        client = TestClient(create_core_app())
        resp = client.get("/static/vendor/htmx.min.js")
        assert resp.status_code == 404


# ---- Contract 3: ui.app is factory-only at module level ------------


class TestUiAppFactoryOnlyContract:
    def test_ui_app_exposes_create_app_callable(self) -> None:
        # Re-import to ensure we're looking at the live module state,
        # not the import-time snapshot from this test file's own
        # imports above.
        importlib.reload(ui.app)
        assert callable(getattr(ui.app, "create_app", None))

    def test_ui_app_does_not_expose_module_level_app(self) -> None:
        """The `app` attribute must NOT exist at module scope. Module-
        level `app = create_app()` is the bug class this contract
        guards against — it instantiates the FastAPI object at import
        time, contaminates test fixtures with duplicate instances when
        ui.app imports core.app, and breaks future config-override
        flexibility. Per DECISIONS `[2026-05-01 Day 10]`."""
        importlib.reload(ui.app)
        assert not hasattr(ui.app, "app"), (
            "ui.app must not expose a module-level `app` attribute. "
            "Use the `create_app()` factory and launch via "
            "`uvicorn ui.app:create_app --factory`."
        )

    def test_core_app_does_not_expose_module_level_app(self) -> None:
        """Same contract for core.app — both apps factory-only per the
        Day 10 mid-Task-0 refactor."""
        import core.app
        importlib.reload(core.app)
        assert not hasattr(core.app, "app"), (
            "core.app must not expose a module-level `app` attribute. "
            "Use the `create_app()` factory and launch via "
            "`uvicorn core.app:create_app --factory`."
        )
