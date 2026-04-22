"""Unit tests for the concierge_request_tool meta-tool handler."""
from __future__ import annotations

import pytest

import httpx

from adapters.claude_code.meta_tools import http_client
from adapters.claude_code.meta_tools.request_tool import (
    handle_request_tool,
    request_tool_spec,
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


class TestRequestToolSpec:
    def test_name_is_concierge_request_tool(self):
        assert request_tool_spec.name == "concierge_request_tool"

    def test_input_schema_requires_tool_name(self):
        assert request_tool_spec.input_schema["required"] == ["tool_name"]

    def test_confidence_has_enum(self):
        confidence_schema = request_tool_spec.input_schema["properties"]["confidence"]
        assert confidence_schema["enum"] == ["high", "medium", "low"]


class TestRequestToolHandlerSuccess:
    @pytest.mark.asyncio
    async def test_success_renders_pinned_confirmation(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "POST"
            assert request.url.path == "/requests"
            return httpx.Response(
                201,
                json={
                    "id": 42,
                    "filename": "2026-04-22-1204-ripgrep.md",
                    "folder": "pending",
                    "status": "pending",
                    "tool_name": "ripgrep",
                    "is_parseable": True,
                },
            )

        _install_mock_transport(mock_handler)
        result = await handle_request_tool(
            {
                "tool_name": "ripgrep",
                "category": "text-processing",
                "confidence": "high",
            }
        )

        assert result["isError"] is False
        text = result["content"][0]["text"]
        assert text.startswith("## Tool request filed")
        assert "**Tool:** ripgrep" in text
        assert "`2026-04-22-1204-ripgrep.md`" in text
        assert "**Folder:** pending" in text
        assert "**Request ID:** 42" in text
        assert "Continue with your current task" in text

    @pytest.mark.asyncio
    async def test_optional_fields_passed_through(self):
        received_body = {}

        def mock_handler(request: httpx.Request) -> httpx.Response:
            import json

            received_body.update(json.loads(request.read().decode()))
            return httpx.Response(
                201,
                json={
                    "id": 1,
                    "filename": "x.md",
                    "folder": "pending",
                    "is_parseable": True,
                },
            )

        _install_mock_transport(mock_handler)
        await handle_request_tool(
            {
                "tool_name": "xsv",
                "category": "data-processing",
                "install_method": "cargo install",
                "task_context": "CSV analysis",
                "why_this_tool": "fast",
                "alternatives_considered": "csvkit, miller",
                "risk_cost": "Free",
                "confidence": "medium",
                "is_discovered": True,
                "source": "awesome-rust",
                "evidence": "5k stars",
            }
        )

        assert received_body["tool_name"] == "xsv"
        assert received_body["install_method"] == "cargo install"
        assert received_body["is_discovered"] is True
        assert received_body["evidence"] == "5k stars"

    @pytest.mark.asyncio
    async def test_null_optional_fields_not_sent(self):
        received_body = {}

        def mock_handler(request: httpx.Request) -> httpx.Response:
            import json

            received_body.update(json.loads(request.read().decode()))
            return httpx.Response(
                201,
                json={
                    "id": 1,
                    "filename": "x.md",
                    "folder": "pending",
                    "is_parseable": True,
                },
            )

        _install_mock_transport(mock_handler)
        await handle_request_tool({"tool_name": "ripgrep", "category": None})

        assert received_body == {"tool_name": "ripgrep"}


class TestRequestToolHandlerFailures:
    @pytest.mark.asyncio
    async def test_service_unavailable(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused", request=request)

        _install_mock_transport(mock_handler)
        result = await handle_request_tool({"tool_name": "ripgrep"})

        assert result["isError"] is True
        assert "Concierge service unavailable" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_filename_collision_409_surfaces_error(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                409,
                json={
                    "detail": {
                        "error": "request_filename_collision",
                        "message": "exists already",
                    }
                },
            )

        _install_mock_transport(mock_handler)
        result = await handle_request_tool({"tool_name": "ripgrep"})

        assert result["isError"] is True
        text = result["content"][0]["text"]
        assert "HTTP 409" in text
        assert "request_filename_collision" in text

    @pytest.mark.asyncio
    async def test_malformed_json(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(201, content=b"not-json")

        _install_mock_transport(mock_handler)
        result = await handle_request_tool({"tool_name": "ripgrep"})

        assert result["isError"] is True
        assert "unexpected response" in result["content"][0]["text"].lower()

    @pytest.mark.asyncio
    async def test_missing_filename_field_malformed(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(201, json={"id": 1})

        _install_mock_transport(mock_handler)
        result = await handle_request_tool({"tool_name": "ripgrep"})

        assert result["isError"] is True
        assert "filename" in result["content"][0]["text"]
