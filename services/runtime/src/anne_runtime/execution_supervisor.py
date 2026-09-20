from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from .contracts import ToolCall
from .isolation import IsolationPolicy, PlatformCapabilities, WorkerDescriptor
from .worker_protocol import PROTOCOL_VERSION, WorkerMessage, WorkerMessageType


class SupervisorInvariantError(RuntimeError):
    """Raised when a supervisor invariant would be violated."""


class SupervisorState(StrEnum):
    NEW = "NEW"
    AUTHORIZED = "AUTHORIZED"
    STARTING = "STARTING"
    READY = "READY"
    RUNNING = "RUNNING"
    CANCELLING = "CANCELLING"
    TIMING_OUT = "TIMING_OUT"
    CRASHED = "CRASHED"
    COMPLETED = "COMPLETED"
    TERMINATING = "TERMINATING"
    CLEANUP = "CLEANUP"
    TERMINAL = "TERMINAL"


_ALLOWED_TRANSITIONS = {
    SupervisorState.NEW: {SupervisorState.AUTHORIZED, SupervisorState.TERMINAL},
    SupervisorState.AUTHORIZED: {SupervisorState.STARTING, SupervisorState.TERMINAL},
    SupervisorState.STARTING: {SupervisorState.READY, SupervisorState.TIMING_OUT, SupervisorState.CRASHED, SupervisorState.TERMINATING, SupervisorState.CLEANUP},
    SupervisorState.READY: {SupervisorState.RUNNING, SupervisorState.CANCELLING, SupervisorState.TERMINATING, SupervisorState.CRASHED},
    SupervisorState.RUNNING: {SupervisorState.CANCELLING, SupervisorState.TIMING_OUT, SupervisorState.CRASHED, SupervisorState.COMPLETED, SupervisorState.TERMINATING},
    SupervisorState.CANCELLING: {SupervisorState.TERMINATING, SupervisorState.CLEANUP},
    SupervisorState.TIMING_OUT: {SupervisorState.TERMINATING, SupervisorState.CLEANUP},
    SupervisorState.CRASHED: {SupervisorState.CLEANUP, SupervisorState.TERMINATING},
    SupervisorState.COMPLETED: {SupervisorState.CLEANUP},
    SupervisorState.TERMINATING: {SupervisorState.CLEANUP},
    SupervisorState.CLEANUP: {SupervisorState.TERMINAL},
    SupervisorState.TERMINAL: set(),
}


@dataclass(frozen=True)
class SupervisorExecution:
    execution_id: UUID
    request_id: UUID
    task_id: UUID
    worker: WorkerDescriptor
    policy: IsolationPolicy
    state: SupervisorState = SupervisorState.NEW
    cleanup_complete: bool = False

    def transition(self, next_state: SupervisorState) -> "SupervisorExecution":
        if next_state not in _ALLOWED_TRANSITIONS[self.state]:
            raise SupervisorInvariantError(f"invalid supervisor transition: {self.state} -> {next_state}")
        return replace(self, state=next_state)

    def mark_cleanup_complete(self) -> "SupervisorExecution":
        if self.state != SupervisorState.CLEANUP:
            raise SupervisorInvariantError("cleanup can only be completed from CLEANUP state")
        return replace(self, state=SupervisorState.TERMINAL, cleanup_complete=True)


class ExecutionSupervisor:
    """Lifecycle and boundary foundation; intentionally does not spawn processes yet."""

    def __init__(self, *, platform_capabilities: PlatformCapabilities | None = None) -> None:
        self._platform_capabilities = platform_capabilities or PlatformCapabilities()
        self._executions: dict[UUID, SupervisorExecution] = {}

    @property
    def platform_capabilities(self) -> PlatformCapabilities:
        return self._platform_capabilities

    def authorize(self, call: ToolCall, worker: WorkerDescriptor, policy: IsolationPolicy, authorization: Any) -> SupervisorExecution:
        if not authorization:
            raise SupervisorInvariantError("execution cannot start without an authorization snapshot")
        if worker.adapter_id != call.tool:
            raise SupervisorInvariantError("worker adapter does not match tool call")
        execution = SupervisorExecution(uuid4(), call.request_id, call.task_id, worker, policy, SupervisorState.AUTHORIZED)
        self._executions[execution.execution_id] = execution
        return execution

    def transition(self, execution_id: UUID, next_state: SupervisorState) -> SupervisorExecution:
        execution = self._get(execution_id)
        updated = execution.transition(next_state)
        self._executions[execution_id] = updated
        return updated

    def cleanup(self, execution_id: UUID) -> SupervisorExecution:
        execution = self._get(execution_id)
        if execution.cleanup_complete:
            return execution
        if execution.state != SupervisorState.CLEANUP:
            execution = execution.transition(SupervisorState.CLEANUP)
        updated = execution.mark_cleanup_complete()
        self._executions[execution_id] = updated
        return updated

    def validate_worker_message(self, execution_id: UUID, message: WorkerMessage, *, expected_sequence: int | None = None) -> None:
        execution = self._get(execution_id)
        message.validate(expected_worker_id=execution.worker.worker_id, max_bytes=execution.policy.max_message_bytes)
        if message.request_id != execution.request_id:
            raise SupervisorInvariantError("worker request correlation mismatch")
        if message.task_id != execution.task_id:
            raise SupervisorInvariantError("worker task correlation mismatch")
        if expected_sequence is not None and message.sequence != expected_sequence:
            raise SupervisorInvariantError("worker message sequence mismatch")

    def build_start_message(self, execution_id: UUID) -> WorkerMessage:
        execution = self._get(execution_id)
        if execution.state != SupervisorState.STARTING:
            raise SupervisorInvariantError("START message requires STARTING state")
        return WorkerMessage(
            protocol_version=PROTOCOL_VERSION,
            request_id=execution.request_id,
            task_id=execution.task_id,
            worker_id=execution.worker.worker_id,
            message_type=WorkerMessageType.START,
            sequence=0,
            payload={
                "adapter_id": execution.worker.adapter_id,
                "adapter_version": execution.worker.adapter_version,
                "runtime_api": execution.worker.runtime_api,
            },
        )

    def get(self, execution_id: UUID) -> SupervisorExecution:
        return self._get(execution_id)

    def _get(self, execution_id: UUID) -> SupervisorExecution:
        try:
            return self._executions[execution_id]
        except KeyError as exc:
            raise SupervisorInvariantError(f"unknown supervisor execution: {execution_id}") from exc
