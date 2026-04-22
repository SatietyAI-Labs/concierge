"""Tests for adapters.claude_code.jsonrpc — Layer 1 codec.

Pure parse/serialize tests; no stdio, no subprocess.
"""
from __future__ import annotations

import json

import pytest

from adapters.claude_code.jsonrpc import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    JsonRpcRequest,
    ParseError,
    make_error_response,
    make_result_response,
    parse_message,
    serialize,
)


class TestParseMessage:
    def test_parses_request_with_int_id(self):
        raw = '{"jsonrpc":"2.0","id":42,"method":"initialize","params":{}}'
        req = parse_message(raw)
        assert req.method == "initialize"
        assert req.id == 42
        assert req.is_notification is False
        assert req.params == {}

    def test_parses_request_with_string_id(self):
        raw = '{"jsonrpc":"2.0","id":"abc","method":"tools/list"}'
        req = parse_message(raw)
        assert req.id == "abc"
        assert req.params is None

    def test_notification_has_no_id(self):
        raw = '{"jsonrpc":"2.0","method":"initialized"}'
        req = parse_message(raw)
        assert req.is_notification is True
        assert req.id is None

    def test_explicit_null_id_not_notification(self):
        """JSON-RPC spec § distinguishes `id` absent from `id:null`.
        MCP uses absent-id for notifications; null-id would be
        anomalous but we still emit a response so the mismatch is
        observable.
        """
        raw = '{"jsonrpc":"2.0","id":null,"method":"x"}'
        req = parse_message(raw)
        assert req.is_notification is False
        assert req.id is None

    def test_params_can_be_list(self):
        raw = '{"jsonrpc":"2.0","id":1,"method":"x","params":["a","b"]}'
        req = parse_message(raw)
        assert req.params == ["a", "b"]

    def test_accepts_bytes(self):
        raw = b'{"jsonrpc":"2.0","id":1,"method":"x"}'
        req = parse_message(raw)
        assert req.method == "x"


class TestParseErrors:
    def test_empty_raises(self):
        with pytest.raises(ParseError, match="empty"):
            parse_message("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ParseError):
            parse_message("   \n\t  ")

    def test_malformed_json_raises(self):
        with pytest.raises(ParseError, match="invalid JSON"):
            parse_message("{not json")

    def test_invalid_utf8_raises(self):
        with pytest.raises(ParseError, match="UTF-8"):
            parse_message(b"\xff\xfe\x00 not utf-8")

    def test_non_object_top_level(self):
        with pytest.raises(ParseError, match="object"):
            parse_message("[1,2,3]")

    def test_missing_jsonrpc_version(self):
        with pytest.raises(ParseError, match="jsonrpc"):
            parse_message('{"id":1,"method":"x"}')

    def test_wrong_jsonrpc_version(self):
        with pytest.raises(ParseError, match="jsonrpc"):
            parse_message('{"jsonrpc":"1.0","id":1,"method":"x"}')

    def test_missing_method(self):
        with pytest.raises(ParseError, match="method"):
            parse_message('{"jsonrpc":"2.0","id":1}')

    def test_non_string_method(self):
        with pytest.raises(ParseError, match="method"):
            parse_message('{"jsonrpc":"2.0","id":1,"method":42}')

    def test_non_container_id(self):
        with pytest.raises(ParseError, match="id"):
            parse_message('{"jsonrpc":"2.0","id":{"obj":true},"method":"x"}')

    def test_non_container_params(self):
        with pytest.raises(ParseError, match="params"):
            parse_message('{"jsonrpc":"2.0","id":1,"method":"x","params":"string"}')


class TestErrorCodes:
    def test_spec_error_codes_defined(self):
        assert PARSE_ERROR == -32700
        assert INVALID_REQUEST == -32600
        assert METHOD_NOT_FOUND == -32601
        assert INVALID_PARAMS == -32602
        assert INTERNAL_ERROR == -32603


class TestResponseBuilders:
    def test_result_response_shape(self):
        resp = make_result_response(42, {"tools": []})
        assert resp == {"jsonrpc": "2.0", "id": 42, "result": {"tools": []}}

    def test_error_response_minimal(self):
        resp = make_error_response(1, METHOD_NOT_FOUND, "no such method")
        assert resp["error"]["code"] == METHOD_NOT_FOUND
        assert resp["error"]["message"] == "no such method"
        assert "data" not in resp["error"]

    def test_error_response_with_data(self):
        resp = make_error_response(
            1, INTERNAL_ERROR, "handler raised", {"trace": "..."}
        )
        assert resp["error"]["data"] == {"trace": "..."}

    def test_error_response_preserves_null_id(self):
        """Parse errors must emit with id=null per JSON-RPC 2.0 §5.1."""
        resp = make_error_response(None, PARSE_ERROR, "invalid JSON")
        assert resp["id"] is None


class TestSerialize:
    def test_single_line_with_newline(self):
        line = serialize({"jsonrpc": "2.0", "id": 1, "result": None})
        assert line.endswith("\n")
        assert line.count("\n") == 1

    def test_compact_separators(self):
        line = serialize({"a": 1, "b": [2, 3]})
        # Compact: no spaces after separators.
        assert ": " not in line
        assert ", " not in line

    def test_roundtrip(self):
        req = parse_message(
            '{"jsonrpc":"2.0","id":"xyz","method":"tools/list","params":{}}'
        )
        # Build a response and re-parse it as a dict to confirm
        # serialization produces valid JSON.
        resp = make_result_response(req.id, {"tools": []})
        line = serialize(resp)
        parsed_back = json.loads(line)
        assert parsed_back["id"] == "xyz"
        assert parsed_back["result"] == {"tools": []}

    def test_utf8_preserved(self):
        line = serialize({"text": "Grace Hopper 🚀"})
        assert "🚀" in line


class TestJsonRpcRequestImmutable:
    def test_frozen_dataclass(self):
        req = JsonRpcRequest(method="x", params=None, id=1, is_notification=False)
        with pytest.raises(Exception):  # FrozenInstanceError
            req.method = "y"  # type: ignore[misc]
