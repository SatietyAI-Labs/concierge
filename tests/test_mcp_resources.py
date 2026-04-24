"""Tests for adapters.claude_code.resources — MCP resources protocol.

Covers Fix Day 4 Task 2 (narration-as-push pattern 2):

- `register_resources` declares the `resources` capability and
  wires the six Concierge prompt resources
- `resources/list` returns the six resources in canonical order
  with correct metadata shape
- `resources/read` returns the verbatim source constant for each
  URI (byte-identity regression guards against silent drift when
  the constant is edited)
- Unknown URIs and bad params surface as INVALID_PARAMS rather
  than INTERNAL_ERROR so the client sees a precise failure locus
- Registration is idempotent so tests / shim restarts don't
  double-register

The verbatim assertions are load-bearing: the X3/X4/X6/X7-A/X8
Class-1 fragments are exposed byte-for-byte per DECISIONS
`[2026-04-21 05:50]` EXTRACT invariant; any paraphrase or reflow
inside resources.py is a bug. The gap-preamble is adapter-authored
but still exposed byte-for-byte from CLAUDE_CODE_GAP_PREAMBLE so
its X8-anchor-phrase drift guard (tests/test_meta_tools_gap_preamble.py)
catches upstream drift.
"""
from __future__ import annotations

import pytest

from adapters.claude_code.dispatcher import (
    Dispatcher,
    PROTOCOL_VERSION,
    ResourceSpec,
    build_default_dispatcher,
)
from adapters.claude_code.jsonrpc import INVALID_PARAMS, JsonRpcRequest
from adapters.claude_code.meta_tools.gap_preamble import CLAUDE_CODE_GAP_PREAMBLE
from adapters.claude_code.resources import CONCIERGE_RESOURCES, register_resources
from core.prompts import (
    TOOL_AWARENESS_BEHAVIORAL_RULES__FROM_SOUL_DELTA_MD,
    TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD,
    TOOL_DISCOVERY_PROTOCOL__FROM_TOOL_DISCOVERY_SKILL,
    TOOL_LIFECYCLE_WEEKLY_REVIEW_PROTOCOL__FROM_TOOL_LIFECYCLE_SKILL,
    TOOL_RECOMMENDATION_PROTOCOL__FROM_TOOL_RECOMMENDATION_MD,
)


EXPECTED_URIS_IN_ORDER = [
    "concierge://prompts/tool-awareness.md",
    "concierge://prompts/tool-recommendation.md",
    "concierge://prompts/tool-discovery.md",
    "concierge://prompts/tool-lifecycle-weekly-review.md",
    "concierge://prompts/behavioral-rules.md",
    "concierge://prompts/gap-preamble.md",
]


# URI → source constant binding. This is the byte-identity contract:
# any change to resources.py that accidentally paraphrases a resource
# body fails the corresponding test_resources_read_is_byte_identical_*
# assertion.
URI_TO_SOURCE = {
    "concierge://prompts/tool-awareness.md":
        TOOL_AWARENESS_PROTOCOL__FROM_TOOL_AWARENESS_MD,
    "concierge://prompts/tool-recommendation.md":
        TOOL_RECOMMENDATION_PROTOCOL__FROM_TOOL_RECOMMENDATION_MD,
    "concierge://prompts/tool-discovery.md":
        TOOL_DISCOVERY_PROTOCOL__FROM_TOOL_DISCOVERY_SKILL,
    "concierge://prompts/tool-lifecycle-weekly-review.md":
        TOOL_LIFECYCLE_WEEKLY_REVIEW_PROTOCOL__FROM_TOOL_LIFECYCLE_SKILL,
    "concierge://prompts/behavioral-rules.md":
        TOOL_AWARENESS_BEHAVIORAL_RULES__FROM_SOUL_DELTA_MD,
    "concierge://prompts/gap-preamble.md":
        CLAUDE_CODE_GAP_PREAMBLE,
}


@pytest.fixture
def dispatcher() -> Dispatcher:
    """A dispatcher with default handlers + registered resources.

    Every resources-protocol test uses this shape; isolating it in a
    fixture keeps tests focused on the behavior under assertion and
    catches drift in the registration path once at collection time.
    """
    d = build_default_dispatcher()
    register_resources(d)
    return d


# ---- Static inventory shape ---------------------------------------------


class TestStaticInventory:
    def test_six_resources_exposed(self):
        assert len(CONCIERGE_RESOURCES) == 6

    def test_uris_in_canonical_order(self):
        """Order is design-intentional per resources.py module
        docstring: three reasoning protocols first, lifecycle review
        fourth, behavioral rules fifth, condensed preamble last.
        """
        assert [r.uri for r in CONCIERGE_RESOURCES] == EXPECTED_URIS_IN_ORDER

    def test_every_resource_is_text_markdown(self):
        for r in CONCIERGE_RESOURCES:
            assert r.mime_type == "text/markdown", (
                f"resource {r.uri} has mime_type={r.mime_type!r}, expected text/markdown"
            )

    def test_every_resource_has_non_empty_body(self):
        for r in CONCIERGE_RESOURCES:
            assert r.text, f"resource {r.uri} has empty body"
            assert len(r.text) > 100, (
                f"resource {r.uri} body suspiciously short "
                f"({len(r.text)} bytes); expected >100"
            )

    def test_every_resource_has_non_empty_description(self):
        for r in CONCIERGE_RESOURCES:
            assert r.description, f"resource {r.uri} has empty description"


# ---- Capability advertisement -------------------------------------------


class TestCapabilityAdvertisement:
    @pytest.mark.asyncio
    async def test_initialize_advertises_resources_capability(self, dispatcher):
        """After register_resources, the `initialize` response must
        include the `resources` capability alongside `tools`.
        """
        req = JsonRpcRequest(
            method="initialize",
            params={"protocolVersion": PROTOCOL_VERSION},
            id=1,
            is_notification=False,
        )
        resp = await dispatcher.dispatch(req)
        capabilities = resp["result"]["capabilities"]
        assert "resources" in capabilities
        assert capabilities["resources"] == {}

    @pytest.mark.asyncio
    async def test_tools_capability_still_present(self, dispatcher):
        """Adding `resources` must not remove `tools`."""
        req = JsonRpcRequest(
            method="initialize",
            params={"protocolVersion": PROTOCOL_VERSION},
            id=1,
            is_notification=False,
        )
        resp = await dispatcher.dispatch(req)
        assert "tools" in resp["result"]["capabilities"]


# ---- resources/list ------------------------------------------------------


class TestResourcesList:
    @pytest.mark.asyncio
    async def test_lists_all_six_resources(self, dispatcher):
        req = JsonRpcRequest(
            method="resources/list", params=None, id=2, is_notification=False
        )
        resp = await dispatcher.dispatch(req)
        assert "result" in resp
        resources = resp["result"]["resources"]
        assert len(resources) == 6

    @pytest.mark.asyncio
    async def test_resources_returned_in_canonical_order(self, dispatcher):
        req = JsonRpcRequest(
            method="resources/list", params=None, id=2, is_notification=False
        )
        resp = await dispatcher.dispatch(req)
        returned_uris = [r["uri"] for r in resp["result"]["resources"]]
        assert returned_uris == EXPECTED_URIS_IN_ORDER

    @pytest.mark.asyncio
    async def test_each_entry_has_required_mcp_fields(self, dispatcher):
        """MCP resources/list entries: uri, name, description, mimeType.
        Text body must NOT be included in the list payload — that's
        what resources/read is for.
        """
        req = JsonRpcRequest(
            method="resources/list", params=None, id=2, is_notification=False
        )
        resp = await dispatcher.dispatch(req)
        for entry in resp["result"]["resources"]:
            assert set(entry.keys()) == {"uri", "name", "description", "mimeType"}
            assert entry["mimeType"] == "text/markdown"

    @pytest.mark.asyncio
    async def test_accepts_object_params_and_ignores_them(self, dispatcher):
        """MCP resources/list is parameter-less; any params shape
        should be accepted and ignored rather than erroring.
        """
        req = JsonRpcRequest(
            method="resources/list",
            params={"cursor": "unused"},
            id=2,
            is_notification=False,
        )
        resp = await dispatcher.dispatch(req)
        assert "result" in resp
        assert len(resp["result"]["resources"]) == 6


# ---- resources/read ------------------------------------------------------


class TestResourcesRead:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("uri", EXPECTED_URIS_IN_ORDER)
    async def test_read_returns_verbatim_source_constant(self, dispatcher, uri):
        """Byte-identity regression guard: every URI must return the
        exact source constant. This catches any future edit that
        accidentally paraphrases a resource body during copy-paste.
        """
        req = JsonRpcRequest(
            method="resources/read",
            params={"uri": uri},
            id=3,
            is_notification=False,
        )
        resp = await dispatcher.dispatch(req)
        contents = resp["result"]["contents"]
        assert len(contents) == 1
        body = contents[0]["text"]
        assert body == URI_TO_SOURCE[uri], (
            f"{uri} body drifted from its source constant — verbatim "
            "invariant violated"
        )

    @pytest.mark.asyncio
    async def test_read_response_shape(self, dispatcher):
        """MCP resources/read result: {contents: [{uri, mimeType, text}]}"""
        req = JsonRpcRequest(
            method="resources/read",
            params={"uri": "concierge://prompts/tool-awareness.md"},
            id=3,
            is_notification=False,
        )
        resp = await dispatcher.dispatch(req)
        assert set(resp["result"].keys()) == {"contents"}
        entry = resp["result"]["contents"][0]
        assert set(entry.keys()) == {"uri", "mimeType", "text"}
        assert entry["uri"] == "concierge://prompts/tool-awareness.md"
        assert entry["mimeType"] == "text/markdown"

    @pytest.mark.asyncio
    async def test_unknown_uri_returns_invalid_params(self, dispatcher):
        """An unknown URI surfaces as INVALID_PARAMS (not INTERNAL_ERROR
        or METHOD_NOT_FOUND) so the client sees a precise failure locus.
        """
        req = JsonRpcRequest(
            method="resources/read",
            params={"uri": "concierge://prompts/does-not-exist.md"},
            id=4,
            is_notification=False,
        )
        resp = await dispatcher.dispatch(req)
        assert resp["error"]["code"] == INVALID_PARAMS
        assert "not registered" in resp["error"]["message"]

    @pytest.mark.asyncio
    async def test_missing_uri_param_returns_invalid_params(self, dispatcher):
        req = JsonRpcRequest(
            method="resources/read",
            params={},
            id=5,
            is_notification=False,
        )
        resp = await dispatcher.dispatch(req)
        assert resp["error"]["code"] == INVALID_PARAMS
        assert "uri" in resp["error"]["message"]

    @pytest.mark.asyncio
    async def test_non_string_uri_returns_invalid_params(self, dispatcher):
        req = JsonRpcRequest(
            method="resources/read",
            params={"uri": 123},
            id=6,
            is_notification=False,
        )
        resp = await dispatcher.dispatch(req)
        assert resp["error"]["code"] == INVALID_PARAMS

    @pytest.mark.asyncio
    async def test_empty_uri_returns_invalid_params(self, dispatcher):
        req = JsonRpcRequest(
            method="resources/read",
            params={"uri": ""},
            id=7,
            is_notification=False,
        )
        resp = await dispatcher.dispatch(req)
        assert resp["error"]["code"] == INVALID_PARAMS

    @pytest.mark.asyncio
    async def test_non_object_params_returns_invalid_params(self, dispatcher):
        req = JsonRpcRequest(
            method="resources/read",
            params="not-an-object",  # type: ignore[arg-type]
            id=8,
            is_notification=False,
        )
        resp = await dispatcher.dispatch(req)
        assert resp["error"]["code"] == INVALID_PARAMS


# ---- Registration idempotency & injection -------------------------------


class TestRegistrationIdempotency:
    @pytest.mark.asyncio
    async def test_double_register_does_not_duplicate_resources(self):
        """Calling register_resources twice on the same dispatcher
        leaves a six-resource registry (keyed by URI; re-registration
        replaces the prior spec in-place rather than duplicating).
        """
        d = build_default_dispatcher()
        register_resources(d)
        register_resources(d)
        req = JsonRpcRequest(
            method="resources/list", params=None, id=1, is_notification=False
        )
        resp = await d.dispatch(req)
        assert len(resp["result"]["resources"]) == 6

    @pytest.mark.asyncio
    async def test_custom_resource_list_can_be_injected(self):
        """register_resources(d, resources=[...]) replaces the default
        inventory — used by any future narrow-scope test or alternate
        deployment that needs a different resource set.
        """
        d = build_default_dispatcher()
        custom = [
            ResourceSpec(
                uri="concierge://prompts/custom.md",
                name="Custom",
                description="For tests.",
                mime_type="text/markdown",
                text="# Custom body\n",
            ),
        ]
        register_resources(d, resources=custom)
        req = JsonRpcRequest(
            method="resources/list", params=None, id=1, is_notification=False
        )
        resp = await d.dispatch(req)
        assert len(resp["result"]["resources"]) == 1
        assert resp["result"]["resources"][0]["uri"] == "concierge://prompts/custom.md"


# ---- ResourceSpec shape -------------------------------------------------


class TestResourceSpec:
    def test_to_mcp_shape_excludes_text(self):
        """resources/list entries must NOT include the resource body
        (clients use resources/read for that). Accidental inclusion
        would bloat every initialize-time listing by ~30 KB.
        """
        spec = ResourceSpec(
            uri="concierge://prompts/x.md",
            name="X",
            description="desc",
            mime_type="text/markdown",
            text="body",
        )
        mcp = spec.to_mcp()
        assert "text" not in mcp
        assert mcp == {
            "uri": "concierge://prompts/x.md",
            "name": "X",
            "description": "desc",
            "mimeType": "text/markdown",
        }

    def test_to_contents_shape_includes_text(self):
        spec = ResourceSpec(
            uri="concierge://prompts/x.md",
            name="X",
            description="desc",
            mime_type="text/markdown",
            text="body",
        )
        contents = spec.to_contents()
        assert contents == {
            "uri": "concierge://prompts/x.md",
            "mimeType": "text/markdown",
            "text": "body",
        }
