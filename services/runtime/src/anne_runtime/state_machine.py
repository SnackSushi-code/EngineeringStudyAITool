from __future__ import annotations

from dataclasses import dataclass

from .contracts import TERMINAL_STATES, TaskState
from .errors import InvalidTransitionError

_ALLOWED: dict[TaskState, frozenset[TaskState]] = {
    TaskState.QUEUED: frozenset({
        TaskState.PLANNING,
        TaskState.CANCELLED,
        TaskState.DENIED,
        TaskState.TIMED_OUT,
    }),
    TaskState.PLANNING: frozenset({
        TaskState.WAITING_APPROVAL,
        TaskState.RUNNING,
        TaskState.FAILED,
        TaskState.DENIED,
        TaskState.CANCELLED,
        TaskState.TIMED_OUT,
    }),
    TaskState.WAITING_APPROVAL: frozenset({
        TaskState.RUNNING,
        TaskState.DENIED,
        TaskState.CANCELLED,
        TaskState.TIMED_OUT,
    }),
    TaskState.RUNNING: frozenset({
        TaskState.VALIDATING,
        TaskState.SUCCEEDED,
        TaskState.FAILED,
        TaskState.CANCELLED,
        TaskState.TIMED_OUT,
    }),
    TaskState.VALIDATING: frozenset({
        TaskState.SUCCEEDED,
        TaskState.FAILED,
        TaskState.ROLLING_BACK,
        TaskState.CANCELLED,
        TaskState.TIMED_OUT,
    }),
    TaskState.ROLLING_BACK: frozenset({
        TaskState.FAILED,
        TaskState.CANCELLED,
        TaskState.TIMED_OUT,
    }),
    TaskState.SUCCEEDED: frozenset(),
    TaskState.FAILED: frozenset(),
    TaskState.CANCELLED: frozenset(),
    TaskState.DENIED: frozenset(),
    TaskState.TIMED_OUT: frozenset(),
}


@dataclass
class TaskStateMachine:
    state: TaskState = TaskState.QUEUED

    def transition(self, target: TaskState) -> TaskState:
        if self.state in TERMINAL_STATES:
            raise InvalidTransitionError(
                f"Terminal task state {self.state} cannot transition to {target}"
            )
        if target not in _ALLOWED[self.state]:
            raise InvalidTransitionError(
                f"Invalid task transition: {self.state} -> {target}"
            )
        self.state = target
        return self.state

    def can_transition(self, target: TaskState) -> bool:
        return target in _ALLOWED[self.state]
