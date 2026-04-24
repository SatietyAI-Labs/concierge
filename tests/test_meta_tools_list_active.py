"""Unit tests for the concierge_list_active meta-tool handler."""
from __future__ import annotations

import pytest

import httpx

from adapters.claude_code.meta_tools import http_client
from adapters.claude_code.meta_tools.list_active import (
    handle_list_active,
    list_active_spec,
)


def _install_mock_transport(handler):
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url=http_client.get_concierge_url(),
        timeout=5.0,
    )
    http_client.set_client_for_tests(client)
    return client


@pytest.fixture(autouse=True)
def _reset_client():
    yield
    http_client.set_client_for_tests(None)


class TestListActiveSpec:
    def test_name_is_concierge_list_active(self):
        assert list_active_spec.name == "concierge_list_active"

    def test_input_schema_has_no_required_fields(self):
        assert list_active_spec.input_schema.get("required", []) == []

    def test_schema_fields_present(self):
        props = list_active_spec.input_schema["properties"]
        assert "category" in props
        assert "pack_slug" in props
        assert "dormant" in props


class TestListActiveHandler:
    @pytest.mark.asyncio
    async def test_default_filters_to_active(self):
        received_params = {}

        def mock_handler(request: httpx.Request) -> httpx.Response:
            received_params.update(dict(request.url.params))
            return httpx.Response(200, json={"items": [], "total": 0})

        _install_mock_transport(mock_handler)
        await handle_list_active({})

        assert received_params.get("is_active") == "true"
        assert "dormant" not in received_params

    @pytest.mark.asyncio
    async def test_dormant_flag_flips_query(self):
        received_params = {}

        def mock_handler(request: httpx.Request) -> httpx.Response:
            received_params.update(dict(request.url.params))
            return httpx.Response(200, json={"items": [], "total": 0})

        _install_mock_transport(mock_handler)
        await handle_list_active({"dormant": True})

        assert received_params.get("dormant") == "true"
        assert "is_active" not in received_params

    @pytest.mark.asyncio
    async def test_pack_grouped_rendering(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": 1,
                            "slug": "csvstat",
                            "name": "csvstat",
                            "description": "Column statistics for CSVs.",
                            "is_in_manifest": True,
                            "is_active": True,
                            "pack_slug": "csvkit",
                            "pack_name": "csvkit",
                            "created_at": "2026-04-21T00:00:00Z",
                            "updated_at": "2026-04-21T00:00:00Z",
                        },
                        {
                            "id": 2,
                            "slug": "pandas",
                            "name": "pandas",
                            "description": "DataFrame toolkit.",
                            "is_in_manifest": True,
                            "is_active": True,
                            "pack_slug": "data-processing",
                            "pack_name": "Data processing",
                            "created_at": "2026-04-21T00:00:00Z",
                            "updated_at": "2026-04-21T00:00:00Z",
                        },
                    ],
                    "total": 2,
                },
            )

        _install_mock_transport(mock_handler)
        result = await handle_list_active({})

        assert result["isError"] is False
        text = result["content"][0]["text"]
        assert text.startswith("## Active tools")
        assert "2 tool(s) across 2 pack(s)" in text
        assert "### csvkit (`csvkit`)" in text
        assert "### Data processing (`data-processing`)" in text
        assert "**`csvstat`**" in text
        assert "Column statistics for CSVs." in text

    @pytest.mark.asyncio
    async def test_unpacked_tools_rendered_in_own_section(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": 1,
                            "slug": "standalone-cli",
                            "name": "standalone-cli",
                            "description": "a loner",
                            "is_in_manifest": True,
                            "is_active": True,
                            "pack_slug": None,
                            "pack_name": None,
                            "created_at": "2026-04-21T00:00:00Z",
                            "updated_at": "2026-04-21T00:00:00Z",
                        }
                    ],
                    "total": 1,
                },
            )

        _install_mock_transport(mock_handler)
        result = await handle_list_active({})

        text = result["content"][0]["text"]
        assert "### (unpacked)" in text
        assert "**`standalone-cli`**" in text

    @pytest.mark.asyncio
    async def test_empty_result_rendered_as_no_active(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"items": [], "total": 0})

        _install_mock_transport(mock_handler)
        result = await handle_list_active({})

        text = result["content"][0]["text"]
        assert result["isError"] is False
        assert "0 tool(s)" in text
        assert "no active tools match" in text

    @pytest.mark.asyncio
    async def test_service_unavailable(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused", request=request)

        _install_mock_transport(mock_handler)
        result = await handle_list_active({})

        assert result["isError"] is True
        assert "Concierge service unavailable" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_5xx_renders_service_error(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="internal server error")

        _install_mock_transport(mock_handler)
        result = await handle_list_active({})

        assert result["isError"] is True
        assert "HTTP 500" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_missing_items_field_malformed(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"total": 0})

        _install_mock_transport(mock_handler)
        result = await handle_list_active({})

        assert result["isError"] is True
        assert "items" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_rich_rendering_includes_lifecycle_state_and_tool_type(self):
        """Fix Day 3 Task 6: list_active rendering must surface
        `lifecycle_state` and `tool_type` per item so Claude can reason
        about the toolbelt's shape without a second call."""
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": 1,
                            "slug": "csvstat",
                            "name": "csvstat",
                            "description": "Column statistics for CSVs.",
                            "tool_type": "cli",
                            "lifecycle_state": "loaded-on-boot",
                            "is_in_manifest": True,
                            "is_active": True,
                            "pack_slug": "csvkit",
                            "pack_name": "csvkit",
                            "created_at": "2026-04-21T00:00:00Z",
                            "updated_at": "2026-04-21T00:00:00Z",
                        },
                        {
                            "id": 2,
                            "slug": "update-config",
                            "name": "update-config",
                            "description": "Configure settings.json.",
                            "tool_type": "skill",
                            "lifecycle_state": "discovered",
                            "is_in_manifest": True,
                            "is_active": True,
                            "pack_slug": None,
                            "pack_name": None,
                            "path": "/mnt/skills/public/update-config/SKILL.md",
                            "ambient_loading": True,
                            "created_at": "2026-04-21T00:00:00Z",
                            "updated_at": "2026-04-21T00:00:00Z",
                        },
                    ],
                    "total": 2,
                },
            )

        _install_mock_transport(mock_handler)
        result = await handle_list_active({})

        text = result["content"][0]["text"]
        assert result["isError"] is False
        # CLI tool: <cli> tag + [loaded-on-boot] state
        assert "<cli>" in text
        assert "[loaded-on-boot]" in text
        # Skill tool: <skill> tag + [discovered] state
        assert "<skill>" in text
        assert "[discovered]" in text

    @pytest.mark.asyncio
    async def test_rich_rendering_degrades_on_missing_annotations(self):
        """Rows without lifecycle_state / tool_type should still render
        cleanly — no crash, just no annotation decorations."""
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": 1,
                            "slug": "legacy-tool",
                            "name": "legacy-tool",
                            "description": "pre-enrichment row",
                            "is_in_manifest": True,
                            "is_active": True,
                            "pack_slug": None,
                            "pack_name": None,
                            "created_at": "2026-04-21T00:00:00Z",
                            "updated_at": "2026-04-21T00:00:00Z",
                        },
                    ],
                    "total": 1,
                },
            )

        _install_mock_transport(mock_handler)
        result = await handle_list_active({})

        text = result["content"][0]["text"]
        assert result["isError"] is False
        assert "**`legacy-tool`**" in text
        # No annotation brackets where data is absent
        assert "<cli>" not in text
        assert "[loaded-on-boot]" not in text
