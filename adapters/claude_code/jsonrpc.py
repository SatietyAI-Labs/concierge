"""JSON-RPC 2.0 codec — pure parse/serialize, no I/O.

Layer 1 of the shim architecture. Separation rationale: the codec
is fully testable without touching stdin/stdout; layers 2+ build
on it.

Spec refs:
- JSON-RPC 2.0: https://www.jsonrpc.org/specification
- MCP framing: one JSON object per line on stdio
  (newline-delimited; no Content-Length headers for stdio transport)

Error codes (JSON-RPC 2.0 + MCP conventions):

  -32700  PARSE_ERROR       invalid JSON
  -32600  INVALID_REQUEST   well-formed JSON but not a valid request
  -32601  METHOD_NOT_FOUND  method does not exist
  -32602  INVALID_PARAMS    invalid method params
  -32603  INTERNAL_ERROR    handler raised
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional, Union


# JSON-RPC 2.0 standard error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


# Id type per JSON-RPC spec: string, number, or null.
IdType = Union[int, str, None]
ParamsType = Union[dict[str, Any], list[Any], None]


class ParseError(ValueError):
    """Raised on malformed JSON or structural violations of the
    JSON-RPC 2.0 request shape. Layer-3 (shim) catches this and
    emits a PARSE_ERROR response with id=null per spec.
    """


@dataclass(frozen=True)
class JsonRpcRequest:
    """Parsed inbound message. `id is None` signals a notification
    (no response expected per JSON-RPC spec).
    """

    method: str
    params: ParamsType
    id: IdType
    is_notification: bool


def parse_message(raw: Union[str, bytes]) -> JsonRpcRequest:
    """Parse one newline-delimited JSON-RPC 2.0 message.

    Raises ParseError on malformed JSON, wrong JSON-RPC version,
    missing method, or non-object top-level. Batched requests
    (an array of objects per JSON-RPC spec §6) are NOT supported —
    MCP uses one message per line; batch is out of scope for the
    shim.
    """
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ParseError(f"invalid UTF-8 bytes: {exc}") from exc
    text = raw.strip()
    if not text:
        raise ParseError("empty message")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ParseError(f"invalid JSON: {exc.msg} at pos {exc.pos}") from exc
    if not isinstance(payload, dict):
        raise ParseError(
            f"top-level JSON must be an object (JSON-RPC 2.0 §4); "
            f"got {type(payload).__name__}"
        )
    jsonrpc = payload.get("jsonrpc")
    if jsonrpc != "2.0":
        raise ParseError(
            f"unsupported or missing jsonrpc version: {jsonrpc!r} (expected '2.0')"
        )
    method = payload.get("method")
    if not isinstance(method, str) or not method:
        raise ParseError("missing or non-string `method`")

    id_raw = payload.get("id", _MISSING)
    if id_raw is _MISSING:
        id_val: IdType = None
        is_notification = True
    else:
        if id_raw is not None and not isinstance(id_raw, (int, str)):
            raise ParseError(
                f"`id` must be a string, number, or null; got {type(id_raw).__name__}"
            )
        id_val = id_raw
        # Per spec, `id=null` on an inbound request is technically
        # allowed but signals a notification-like with the caller
        # not expecting a response; MCP doesn't use that pattern.
        # We treat id=null as "not a notification" so responses
        # still emit — the client either ignores them or surfaces
        # the mismatch, which is observable.
        is_notification = False

    params = payload.get("params")
    if params is not None and not isinstance(params, (dict, list)):
        raise ParseError(
            f"`params` must be an object, array, or absent; got {type(params).__name__}"
        )

    return JsonRpcRequest(
        method=method, params=params, id=id_val, is_notification=is_notification
    )


_MISSING = object()


def make_result_response(id: IdType, result: Any) -> dict[str, Any]:
    """Build a success response dict per JSON-RPC 2.0 §5."""
    return {"jsonrpc": "2.0", "id": id, "result": result}


def make_error_response(
    id: IdType,
    code: int,
    message: str,
    data: Optional[Any] = None,
) -> dict[str, Any]:
    """Build an error response dict per JSON-RPC 2.0 §5.1.

    `data` is optional; included only if non-None so the wire
    surface stays minimal.
    """
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": id, "error": error}


def serialize(message: dict[str, Any]) -> str:
    """Serialize one response message as a newline-terminated JSON
    line. Uses `separators=(',', ':')` to produce compact output
    (one line per message, no embedded newlines inside values).
    """
    return json.dumps(message, separators=(",", ":"), ensure_ascii=False) + "\n"
