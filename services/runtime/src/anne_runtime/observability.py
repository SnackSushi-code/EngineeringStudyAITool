from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID

from .redaction import redact


@dataclass(frozen=True)
class RuntimeEvent:
    name: str
    occurred_at: str
    request_id: UUID | None = None
    task_id: UUID | None = None
    fields: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "occurred_at": self.occurred_at,
            "request_id": str(self.request_id) if self.request_id else None,
            "task_id": str(self.task_id) if self.task_id else None,
            "fields": redact(self.fields),
        }


class EventSink(Protocol):
    def emit(self, event: RuntimeEvent) -> None:
        ...


class InMemoryEventSink:
    def __init__(self) -> None:
        self._events: list[RuntimeEvent] = []

    def emit(self, event: RuntimeEvent) -> None:
        self._events.append(event)

    def events(self) -> tuple[RuntimeEvent, ...]:
        return tuple(self._events)


class RuntimeTelemetry:
    def __init__(self, sink: EventSink) -> None:
        self._sink = sink

    def emit(
        self,
        name: str,
        *,
        request_id: UUID | None = None,
        task_id: UUID | None = None,
        fields: dict[str, Any] | None = None,
    ) -> RuntimeEvent:
        event = RuntimeEvent(
            name=name,
            occurred_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            request_id=request_id,
            task_id=task_id,
            fields=fields or {},
        )
        self._sink.emit(event)
        return event
