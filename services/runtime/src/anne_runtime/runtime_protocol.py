from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping
from uuid import UUID


PROTOCOL_VERSION = "1.0"


class RuntimeProtocolError(ValueError):
    """Raised when a runtime protocol message is invalid."""


@dataclass(frozen=True)
class RuntimeRequest:
    request_id: str
    task_id: str
    operation: str
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        _validate_uuid(self.request_id, "request_id")
        _validate_uuid(self.task_id, "task_id")

        if not self.operation.strip():
            raise RuntimeProtocolError("operation must not be blank")

        if not isinstance(self.payload, Mapping):
            raise RuntimeProtocolError("payload must be an object")

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol_version": PROTOCOL_VERSION,
            "type": "request",
            "request_id": self.request_id,
            "task_id": self.task_id,
            "operation": self.operation,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True)
class RuntimeResponse:
    request_id: str
    task_id: str
    status: str
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        _validate_uuid(self.request_id, "request_id")
        _validate_uuid(self.task_id, "task_id")

        if self.status not in {
            "accepted",
            "completed",
            "failed",
            "cancelled",
        }:
            raise RuntimeProtocolError(
                f"unsupported response status: {self.status}"
            )

        if not isinstance(self.payload, Mapping):
            raise RuntimeProtocolError("payload must be an object")

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol_version": PROTOCOL_VERSION,
            "type": "response",
            "request_id": self.request_id,
            "task_id": self.task_id,
            "status": self.status,
            "payload": dict(self.payload),
        }


def encode_message(message: RuntimeRequest | RuntimeResponse) -> str:
    """Serialize exactly one protocol message as JSON."""
    return json.dumps(
        message.to_dict(),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def decode_request(raw: str | bytes) -> RuntimeRequest:
    """Decode and validate one runtime request."""
    data = _decode_json_object(raw)

    _require_exact_keys(
        data,
        {
            "protocol_version",
            "type",
            "request_id",
            "task_id",
            "operation",
            "payload",
        },
    )

    if data["protocol_version"] != PROTOCOL_VERSION:
        raise RuntimeProtocolError(
            "unsupported protocol_version: "
            f"{data['protocol_version']!r}"
        )

    if data["type"] != "request":
        raise RuntimeProtocolError(
            f"expected message type 'request', got {data['type']!r}"
        )

    if not isinstance(data["request_id"], str):
        raise RuntimeProtocolError("request_id must be a string")

    if not isinstance(data["task_id"], str):
        raise RuntimeProtocolError("task_id must be a string")

    if not isinstance(data["operation"], str):
        raise RuntimeProtocolError("operation must be a string")

    if not isinstance(data["payload"], Mapping):
        raise RuntimeProtocolError("payload must be an object")

    return RuntimeRequest(
        request_id=data["request_id"],
        task_id=data["task_id"],
        operation=data["operation"],
        payload=dict(data["payload"]),
    )


def decode_response(raw: str | bytes) -> RuntimeResponse:
    """Decode and validate one runtime response."""
    data = _decode_json_object(raw)

    _require_exact_keys(
        data,
        {
            "protocol_version",
            "type",
            "request_id",
            "task_id",
            "status",
            "payload",
        },
    )

    if data["protocol_version"] != PROTOCOL_VERSION:
        raise RuntimeProtocolError(
            "unsupported protocol_version: "
            f"{data['protocol_version']!r}"
        )

    if data["type"] != "response":
        raise RuntimeProtocolError(
            f"expected message type 'response', got {data['type']!r}"
        )

    if not isinstance(data["request_id"], str):
        raise RuntimeProtocolError("request_id must be a string")

    if not isinstance(data["task_id"], str):
        raise RuntimeProtocolError("task_id must be a string")

    if not isinstance(data["status"], str):
        raise RuntimeProtocolError("status must be a string")

    if not isinstance(data["payload"], Mapping):
        raise RuntimeProtocolError("payload must be an object")

    return RuntimeResponse(
        request_id=data["request_id"],
        task_id=data["task_id"],
        status=data["status"],
        payload=dict(data["payload"]),
    )


def _decode_json_object(raw: str | bytes) -> dict[str, Any]:
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeProtocolError(
            f"invalid JSON: {exc.msg}"
        ) from exc

    if not isinstance(decoded, dict):
        raise RuntimeProtocolError("protocol message must be a JSON object")

    return decoded


def _require_exact_keys(
    data: Mapping[str, Any],
    expected: set[str],
) -> None:
    actual = set(data.keys())

    missing = expected - actual
    unknown = actual - expected

    if missing:
        raise RuntimeProtocolError(
            "missing protocol fields: "
            + ", ".join(sorted(missing))
        )

    if unknown:
        raise RuntimeProtocolError(
            "unknown protocol fields: "
            + ", ".join(sorted(unknown))
        )


def _validate_uuid(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise RuntimeProtocolError(
            f"{field_name} must be a UUID string"
        )

    try:
        UUID(value)
    except ValueError as exc:
        raise RuntimeProtocolError(
            f"{field_name} must be a valid UUID"
        ) from exc
