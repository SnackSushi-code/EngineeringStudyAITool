from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Callable
from uuid import UUID

from .contracts import TaskState
from .errors import InvalidTransitionError, RuntimeInvariantError
from .state_machine import TaskStateMachine


@dataclass(frozen=True)
class LifecycleEvent:
    task_id: UUID
    request_id: UUID
    state: TaskState
    timestamp: str
    sequence: int
    detail: str | None = None


@dataclass
class TaskLifecycle:
    request_id: UUID
    task_id: UUID
    machine: TaskStateMachine = field(default_factory=TaskStateMachine)
    _events: list[LifecycleEvent] = field(default_factory=list, init=False)
    _sequence: int = field(default=0, init=False)
    _lock: Lock = field(default_factory=Lock, init=False)
    _listeners: list[Callable[[LifecycleEvent], None]] = field(default_factory=list, init=False)

    def subscribe(self, listener: Callable[[LifecycleEvent], None]) -> None:
        with self._lock:
            self._listeners.append(listener)

    @property
    def state(self) -> TaskState:
        with self._lock:
            return self.machine.state

    def transition(self, target: TaskState, detail: str | None = None) -> LifecycleEvent:
        with self._lock:
            previous = self.machine.state
            try:
                self.machine.transition(target)
            except InvalidTransitionError:
                raise
            self._sequence += 1
            event = LifecycleEvent(
                task_id=self.task_id,
                request_id=self.request_id,
                state=target,
                timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                sequence=self._sequence,
                detail=detail,
            )
            self._events.append(event)
            listeners = tuple(self._listeners)
        for listener in listeners:
            listener(event)
        return event

    def events(self) -> tuple[LifecycleEvent, ...]:
        with self._lock:
            return tuple(self._events)

    def require_state(self, *allowed: TaskState) -> None:
        if self.state not in allowed:
            raise RuntimeInvariantError(
                f"Task {self.task_id} expected one of {allowed}, got {self.state}"
            )
