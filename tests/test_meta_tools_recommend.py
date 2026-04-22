"""Unit tests for the concierge_recommend meta-tool handler.

Covers the ToolSpec shape + the handler's five outcome classes:
success, service-down, HTTP error, malformed JSON, malformed shape.
Uses `httpx.MockTransport` for HTTP mocking (no respx dependency).
"""
from __future__ import annotations

import pytest

import httpx

from adapters.claude_code.meta_tools import http_client
from adapters.claude_code.meta_tools.recommend import (
    handle_recommend,
    recommend_spec,
)


def _install_mock_transport(handler):
    """Swap in a mock-backed AsyncClient for one test. Callers must
    unset in teardown via `set_client_for_tests(None)`.
    """
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


# ---- ToolSpec ------------------------------------------------------------


class TestRecommendSpec:
    def test_name_is_concierge_recommend(self):
        assert recommend_spec.name == "concierge_recommend"

    def test_description_mentions_tool_recommendation(self):
        assert "recommend" in recommend_spec.description.lower()

    def test_input_schema_requires_task(self):
        assert recommend_spec.input_schema["required"] == ["task"]
        assert "task" in recommend_spec.input_schema["properties"]

    def test_input_schema_optional_fields_present(self):
        props = recommend_spec.input_schema["properties"]
        assert "cwd" in props
        assert "task_hint" in props
        assert "active_tools" in props
        assert props["active_tools"]["type"] == "array"
        assert props["active_tools"]["items"]["type"] == "string"


# ---- Handler success path ------------------------------------------------


class TestRecommendHandlerSuccess:
    @pytest.mark.asyncio
    async def test_result_contains_gap_report_section(self):
        """N12: every concierge_recommend success result carries a
        `### Gap report` section between Top-ranked and Summary. Pinned-
        always presence per the N12 Q1 answer (soak-diagnostic clarity).
        """
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "request_id": "gap_report_test_" + "0" * 8,
                    "recommendations": [
                        {
                            "rank": 1,
                            "tool_slug": "csvkit",
                            "tool_name": "csvkit",
                            "rationale": "fits the task",
                            "confidence": "high",
                            "is_in_catalog": True,
                        }
                    ],
                    "memory_available": True,
                    "memory_hit_count": 2,
                    "model": "claude-opus-4-7",
                    "effort": "xhigh",
                    "latency_ms": {"total": 0, "memory": 0, "model": 0, "parse": 0},
                    "token_usage": {"input": 0, "output": 0, "total": 0},
                },
            )

        _install_mock_transport(mock_handler)
        result = await handle_recommend({"task": "task"})

        text = result["content"][0]["text"]
        assert "### Gap report" in text
        # Minimal-block path: no gaps detected (in-catalog, high-conf,
        # memory-backed).
        assert "No gaps detected" in text

    @pytest.mark.asyncio
    async def test_gap_report_ordered_between_top_ranked_and_summary(self):
        """N12 pinned grammar: `## Recommendations → ### Top-ranked →
        ### Gap report → ### Summary`. Future consumers (UI, soak-log
        parsers) rely on this ordering.
        """
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "request_id": "order" + "0" * 19,
                    "recommendations": [
                        {
                            "rank": 1,
                            "tool_slug": None,
                            "tool_name": "xsv",
                            "rationale": "fast CSV",
                            "confidence": "medium",
                            "is_in_catalog": False,
                        }
                    ],
                    "memory_available": True,
                    "memory_hit_count": 0,
                    "model": "claude-opus-4-7",
                    "effort": "xhigh",
                    "latency_ms": {"total": 0, "memory": 0, "model": 0, "parse": 0},
                    "token_usage": {"input": 0, "output": 0, "total": 0},
                },
            )

        _install_mock_transport(mock_handler)
        result = await handle_recommend({"task": "csv"})

        text = result["content"][0]["text"]
        idx_rec = text.index("## Recommendations")
        idx_top = text.index("### Top-ranked")
        idx_gap = text.index("### Gap report")
        idx_sum = text.index("### Summary")
        assert idx_rec < idx_top < idx_gap < idx_sum

    @pytest.mark.asyncio
    async def test_discovery_triggers_not_in_catalog_subsection_in_result(self):
        """End-to-end check that a discovery recommendation surfaces
        in the `### Gap report` section as `#### Not in catalog`.
        This is what N14 integration smoke exercises.
        """
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "request_id": "disc_" + "0" * 19,
                    "recommendations": [
                        {
                            "rank": 1,
                            "tool_slug": None,
                            "tool_name": "xsv",
                            "rationale": "fast CSV",
                            "confidence": "medium",
                            "is_in_catalog": False,
                        }
                    ],
                    "memory_available": True,
                    "memory_hit_count": 0,
                    "model": "claude-opus-4-7",
                    "effort": "xhigh",
                    "latency_ms": {"total": 0, "memory": 0, "model": 0, "parse": 0},
                    "token_usage": {"input": 0, "output": 0, "total": 0},
                },
            )

        _install_mock_transport(mock_handler)
        result = await handle_recommend({"task": "csv"})

        text = result["content"][0]["text"]
        # Gap-report sub-section fires for the discovery
        assert "#### Not in catalog" in text
        assert "#### Suggested next action" in text
        # The preamble's do-not-block voice appears in the SNA text
        gap_section = text[text.index("### Gap report"):text.index("### Summary")]
        assert "concierge_request_tool" in gap_section

    @pytest.mark.asyncio
    async def test_success_renders_pinned_markdown(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "POST"
            assert request.url.path == "/recommend"
            body = request.read().decode()
            assert '"task"' in body
            return httpx.Response(
                200,
                json={
                    "request_id": "abcdef012345-678910",
                    "recommendations": [
                        {
                            "rank": 1,
                            "tool_slug": "csvkit",
                            "tool_name": "csvkit",
                            "rationale": "lightweight CSV CLI",
                            "confidence": "high",
                            "is_in_catalog": True,
                        }
                    ],
                    "memory_available": True,
                    "memory_hit_count": 2,
                    "model": "claude-opus-4-7",
                    "effort": "xhigh",
                    "latency_ms": {"total": 1, "memory": 0, "model": 0, "parse": 0},
                    "token_usage": {"input": 0, "output": 0, "total": 0},
                    "reasoning": "csvkit matches the task pattern.",
                    "stop_reason": "end_turn",
                },
            )

        _install_mock_transport(mock_handler)
        result = await handle_recommend({"task": "analyze a CSV"})

        assert result["isError"] is False
        assert len(result["content"]) == 1
        text = result["content"][0]["text"]
        # Pinned structure — H2 title, H3 sections, ordering
        assert text.startswith("## Recommendations")
        assert "### Top-ranked" in text
        assert "### Summary" in text
        # Top-ranked appears BEFORE Summary — N12's insertion-point contract
        assert text.index("### Top-ranked") < text.index("### Summary")
        # Content rendered
        assert "**csvkit**" in text
        assert "lightweight CSV CLI" in text
        assert "catalog: yes" in text
        assert "slug: `csvkit`" in text
        assert "confidence: high" in text
        assert "csvkit matches the task pattern." in text
        # Request ID is shortened in the context line
        assert "request_id=abcdef012345" in text

    @pytest.mark.asyncio
    async def test_discovery_recommendation_labelled_correctly(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "request_id": "x" * 24,
                    "recommendations": [
                        {
                            "rank": 1,
                            "tool_slug": None,
                            "tool_name": "xsv",
                            "rationale": "Rust CSV CLI",
                            "confidence": "medium",
                            "is_in_catalog": False,
                        }
                    ],
                    "memory_available": True,
                    "memory_hit_count": 0,
                    "model": "claude-opus-4-7",
                    "effort": "xhigh",
                    "latency_ms": {"total": 0, "memory": 0, "model": 0, "parse": 0},
                    "token_usage": {"input": 0, "output": 0, "total": 0},
                    "reasoning": None,
                    "stop_reason": "end_turn",
                },
            )

        _install_mock_transport(mock_handler)
        result = await handle_recommend({"task": "csv work"})

        text = result["content"][0]["text"]
        assert "**xsv**" in text
        assert "catalog: discovery" in text
        assert "slug:" not in text  # discovery case has no slug tag
        assert "*(no summary provided)*" in text

    @pytest.mark.asyncio
    async def test_empty_recommendations_renders_no_gap_message(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "request_id": "none" + "0" * 12,
                    "recommendations": [],
                    "memory_available": True,
                    "memory_hit_count": 0,
                    "model": "claude-opus-4-7",
                    "effort": "xhigh",
                    "latency_ms": {"total": 0, "memory": 0, "model": 0, "parse": 0},
                    "token_usage": {"input": 0, "output": 0, "total": 0},
                },
            )

        _install_mock_transport(mock_handler)
        result = await handle_recommend({"task": "trivial"})

        text = result["content"][0]["text"]
        assert result["isError"] is False
        assert "*(no recommendations returned" in text

    @pytest.mark.asyncio
    async def test_optional_fields_passed_through(self):
        received_body = {}

        def mock_handler(request: httpx.Request) -> httpx.Response:
            import json

            received_body.update(json.loads(request.read().decode()))
            return httpx.Response(
                200,
                json={
                    "request_id": "x" * 24,
                    "recommendations": [],
                    "memory_available": True,
                    "memory_hit_count": 0,
                    "model": "claude-opus-4-7",
                    "effort": "xhigh",
                    "latency_ms": {"total": 0, "memory": 0, "model": 0, "parse": 0},
                    "token_usage": {"input": 0, "output": 0, "total": 0},
                },
            )

        _install_mock_transport(mock_handler)
        await handle_recommend(
            {
                "task": "analyze a CSV",
                "cwd": "/tmp/work",
                "task_hint": "data-analysis",
                "active_tools": ["pandas", "csvkit"],
            }
        )

        assert received_body["task"] == "analyze a CSV"
        assert received_body["cwd"] == "/tmp/work"
        assert received_body["task_hint"] == "data-analysis"
        assert received_body["active_tools"] == ["pandas", "csvkit"]

    @pytest.mark.asyncio
    async def test_memory_unavailable_renders_in_context_line(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "request_id": "mem_outage_" + "0" * 13,
                    "recommendations": [],
                    "memory_available": False,
                    "memory_hit_count": 0,
                    "model": "claude-opus-4-7",
                    "effort": "xhigh",
                    "latency_ms": {"total": 0, "memory": 0, "model": 0, "parse": 0},
                    "token_usage": {"input": 0, "output": 0, "total": 0},
                },
            )

        _install_mock_transport(mock_handler)
        result = await handle_recommend({"task": "task"})

        text = result["content"][0]["text"]
        assert "memory_available=False" in text


# ---- Handler failure paths -----------------------------------------------


class TestRecommendHandlerFailures:
    @pytest.mark.asyncio
    async def test_service_unavailable_renders_actionable_error(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        _install_mock_transport(mock_handler)
        result = await handle_recommend({"task": "task"})

        assert result["isError"] is True
        text = result["content"][0]["text"]
        assert "Concierge service unavailable" in text
        assert "ConnectError" in text
        assert "CONCIERGE_URL" in text

    @pytest.mark.asyncio
    async def test_timeout_mapped_to_service_unavailable(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("slow backing service", request=request)

        _install_mock_transport(mock_handler)
        result = await handle_recommend({"task": "task"})

        assert result["isError"] is True
        assert "Concierge service unavailable" in result["content"][0]["text"]
        assert "ReadTimeout" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_5xx_renders_service_error(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                502,
                json={"detail": {"error": "anthropic_client_failed", "message": "timeout"}},
            )

        _install_mock_transport(mock_handler)
        result = await handle_recommend({"task": "task"})

        assert result["isError"] is True
        text = result["content"][0]["text"]
        assert "Concierge service returned an error" in text
        assert "HTTP 502" in text
        assert "anthropic_client_failed" in text

    @pytest.mark.asyncio
    async def test_malformed_json_renders_malformed_response(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"<html>nope</html>")

        _install_mock_transport(mock_handler)
        result = await handle_recommend({"task": "task"})

        assert result["isError"] is True
        text = result["content"][0]["text"]
        assert "unexpected response" in text.lower()
        assert "not valid JSON" in text or "JSON" in text

    @pytest.mark.asyncio
    async def test_missing_recommendations_field_renders_malformed(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "ok"})

        _install_mock_transport(mock_handler)
        result = await handle_recommend({"task": "task"})

        assert result["isError"] is True
        assert "recommendations" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_unexpected_exception_renders_unavailable_not_crash(self):
        def mock_handler(request: httpx.Request) -> httpx.Response:
            raise RuntimeError("weird internal state")

        _install_mock_transport(mock_handler)
        result = await handle_recommend({"task": "task"})

        assert result["isError"] is True
        assert "unavailable" in result["content"][0]["text"].lower()
        assert "RuntimeError" in result["content"][0]["text"]
