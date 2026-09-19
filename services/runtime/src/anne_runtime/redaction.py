from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "token",
    "secret",
    "private_key",
    "privatekey",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "refresh_token",
    "access_token",
)


def redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        output: dict[Any, Any] = {}
        for key, item in value.items():
            key_text = str(key).lower().replace("-", "_")
            if any(part in key_text for part in SENSITIVE_KEY_PARTS):
                output[key] = "[REDACTED]"
            else:
                output[key] = redact(item)
        return output

    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return [redact(item) for item in value]

    return value
