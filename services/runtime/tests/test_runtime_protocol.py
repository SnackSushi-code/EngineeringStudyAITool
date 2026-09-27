from __future__ import annotations

import json
from uuid import uuid4

import pytest

from anne_runtime.runtime_protocol import (
    PROTOCOL_VERSION,
    RuntimeProtocolError,
    RuntimeRequest,
    RuntimeResponse,
    decode_request,
    decode_response,
    encode_message,
)


def test_request_round_trip() -> None:
    request_id = str(uuid4())
    task_id = str(uuid4())

    request = RuntimeRequest(
        request_id=request_id,
        task_id=task_id,
        operation="health",
        payload={"detail": True},
    )

    encoded = encode_message(request)
    decoded = decode_request(encoded)

    assert decoded == request
    assert json.loads(encoded)["protocol_version"] == PROTOCOL_VERSION
    assert json.loads(encoded)["type"] == "request"


def test_response_round_trip() -> None:
    request_id = str(uuid4())
    task_id = str(uuid4())

    response = RuntimeResponse(
        request_id=request_id,
        task_id=task_id,
        status="completed",
        payload={"runtime_version": "0.5.1"},
    )

    encoded = encode_message(response)
    decoded = decode_response(encoded)

    assert decoded == response
    assert json.loads(encoded)["protocol_version"] == PROTOCOL_VERSION
    assert json.loads(encoded)["type"] == "response"


def test_request_rejects_unknown_fields() -> None:
    raw = json.dumps(
        {
            "protocol_version": PROTOCOL_VERSION,
            "type": "request",
            "request_id": str(uuid4()),
            "task_id": str(uuid4()),
            "operation": "health",
            "payload": {},
            "permissions": ["filesystem.read"],
        }
    )

    with pytest.raises(RuntimeProtocolError, match="unknown protocol fields"):
        decode_request(raw)


def test_request_rejects_missing_fields() -> None:
    raw = json.dumps(
        {
            "protocol_version": PROTOCOL_VERSION,
            "type": "request",
            "request_id": str(uuid4()),
        }
    )

    with pytest.raises(RuntimeProtocolError, match="missing protocol fields"):
        decode_request(raw)


def test_request_rejects_invalid_protocol_version() -> None:
    raw = json.dumps(
        {
            "protocol_version": "999.0",
            "type": "request",
            "request_id": str(uuid4()),
            "task_id": str(uuid4()),
            "operation": "health",
            "payload": {},
        }
    )

    with pytest.raises(
        RuntimeProtocolError,
        match="unsupported protocol_version",
    ):
        decode_request(raw)


def test_request_rejects_invalid_uuid() -> None:
    raw = json.dumps(
        {
            "protocol_version": PROTOCOL_VERSION,
            "type": "request",
            "request_id": "not-a-uuid",
            "task_id": str(uuid4()),
            "operation": "health",
            "payload": {},
        }
    )

    with pytest.raises(
        RuntimeProtocolError,
        match="request_id must be a valid UUID",
    ):
        decode_request(raw)


def test_request_rejects_blank_operation() -> None:
    with pytest.raises(
        RuntimeProtocolError,
        match="operation must not be blank",
    ):
        RuntimeRequest(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            operation="   ",
            payload={},
        )


def test_response_rejects_unknown_status() -> None:
    with pytest.raises(
        RuntimeProtocolError,
        match="unsupported response status",
    ):
        RuntimeResponse(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            status="exploded",
            payload={},
        )


def test_response_rejects_unknown_fields() -> None:
    raw = json.dumps(
        {
            "protocol_version": PROTOCOL_VERSION,
            "type": "response",
            "request_id": str(uuid4()),
            "task_id": str(uuid4()),
            "status": "completed",
            "payload": {},
            "permissions": ["admin"],
        }
    )

    with pytest.raises(RuntimeProtocolError, match="unknown protocol fields"):
        decode_response(raw)


def test_decode_rejects_non_object_json() -> None:
    with pytest.raises(
        RuntimeProtocolError,
        match="must be a JSON object",
    ):
        decode_request("[]")


def test_decode_rejects_invalid_json() -> None:
    with pytest.raises(
        RuntimeProtocolError,
        match="invalid JSON",
    ):
        decode_request("{not-json")


def test_payload_must_be_object() -> None:
    raw = json.dumps(
        {
            "protocol_version": PROTOCOL_VERSION,
            "type": "request",
            "request_id": str(uuid4()),
            "task_id": str(uuid4()),
            "operation": "health",
            "payload": [],
        }
    )

    with pytest.raises(
        RuntimeProtocolError,
        match="payload must be an object",
    ):
        decode_request(raw)
