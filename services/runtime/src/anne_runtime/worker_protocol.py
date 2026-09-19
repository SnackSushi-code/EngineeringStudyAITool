from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID
import json


PROTOCOL_VERSION = "0.1"


class WorkerMessageType(StrEnum):
    START = "START"
    READY = "READY"
    EXECUTE = "EXECUTE"
    RESULT = "RESULT"
    CANCEL = "CANCEL"
    SHUTDOWN = "SHUTDOWN"
    ERROR = "ERROR"


@dataclass(frozen=True)
class WorkerMessage:
    protocol_version: str
    request_id: UUID
    task_id: UUID
    worker_id: str
    message_type: WorkerMessageType
    sequence: int
    payload: dict[str, Any]

    def validate(self, *, expected_worker_id: str, max_bytes: int) -> None:
        if self.protocol_version != PROTOCOL_VERSION:
            raise ValueError("unsupported worker protocol version")
        if self.worker_id != expected_worker_id:
            raise ValueError("worker identity mismatch")
        if self.sequence < 0:
            raise ValueError("sequence must be non-negative")
        if not isinstance(self.message_type, WorkerMessageType):
            raise ValueError("invalid worker message type")
        if not isinstance(self.payload, dict):
            raise ValueError("worker message payload must be an object")
        encoded = json.dumps(self.payload, separators=(",", ":")).encode("utf-8")
        if len(encoded) > max_bytes:
            raise ValueError("worker message exceeds configured maximum size")

    def correlation_key(self) -> tuple[UUID, UUID, str]:
        return self.request_id, self.task_id, self.worker_id
