from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from .contracts import ToolCall
from .isolation import IsolationPolicy, PlatformCapabilities, WorkerDescriptor
from .platform_enforcement import (
    EnforcementRequest,
    PlatformEnforcementAdapter,
    PreparedEnforcement,
)
from .worker_process import WorkerProcess
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
    prepared_enforcement: PreparedEnforcement | None = None

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

    def __init__(
        self,
        *,
        platform_capabilities: PlatformCapabilities | None = None,
        enforcement_adapter: PlatformEnforcementAdapter | None = None,
    ) -> None:
        self._platform_capabilities = platform_capabilities or PlatformCapabilities()
        self._enforcement_adapter = enforcement_adapter
        self._executions: dict[UUID, SupervisorExecution] = {}
        self._workers: dict[UUID, WorkerProcess] = {}

    @property
    def platform_capabilities(self) -> PlatformCapabilities:
        return self._platform_capabilities

    @property
    def enforcement_adapter(self) -> PlatformEnforcementAdapter | None:
        return self._enforcement_adapter

    def prepare_enforcement(
        self,
        execution_id: UUID,
    ) -> PreparedEnforcement:
        execution = self._get(execution_id)

        if execution.state != SupervisorState.AUTHORIZED:
            raise SupervisorInvariantError(
                "enforcement preparation requires AUTHORIZED state"
            )

        if self._enforcement_adapter is None:
            raise SupervisorInvariantError(
                "no platform enforcement adapter is configured"
            )

        request = EnforcementRequest(
            execution_id=execution.execution_id,
            request_id=execution.request_id,
            task_id=execution.task_id,
            worker=execution.worker,
            policy=execution.policy,
        )

        prepared = self._enforcement_adapter.prepare(request)

        self._executions[execution_id] = replace(
            execution,
            prepared_enforcement=prepared,
        )

        return prepared

    def start_worker(
        self,
        execution_id: UUID,
        worker: WorkerProcess,
        *,
        startup_timeout: float | None = None,
    ) -> WorkerMessage:
        execution = self._get(execution_id)

        if execution.state != SupervisorState.AUTHORIZED:
            raise SupervisorInvariantError(
                "worker start requires AUTHORIZED state"
            )

        if self._enforcement_adapter is not None:
            if execution.prepared_enforcement is None:
                self.prepare_enforcement(execution_id)

            execution = self._get(execution_id)

        self.transition(execution_id, SupervisorState.STARTING)

        self._workers[execution_id] = worker

        def process_started(process_handle: int) -> None:
            current = self._get(execution_id)

            if (
                self._enforcement_adapter is not None
                and current.prepared_enforcement is not None
            ):
                self._enforcement_adapter.assign_process(
                    current.prepared_enforcement,
                    process_handle,
                )

        try:
            start_message = worker.start(
                self.build_start_message(execution_id),
                timeout_seconds=(
                    startup_timeout
                    if startup_timeout is not None
                    else self._get(execution_id).policy.timeout_seconds
                ),
                process_started=process_started,
            )

            current = self._get(execution_id)
            if current.state != SupervisorState.STARTING:
                raise SupervisorInvariantError(
                    "worker startup completed outside STARTING state"
                )

            self._executions[execution_id] = current.transition(
                SupervisorState.READY
            )

            return start_message

        except BaseException:
            cleanup_error: BaseException | None = None

            try:
                worker.terminate()
            except BaseException as exc:
                cleanup_error = exc
            finally:
                try:
                    worker.close()
                finally:
                    self._release_enforcement(execution_id)
                    self._workers.pop(execution_id, None)

                    current = self._get(execution_id)

                    if current.state != SupervisorState.CLEANUP:
                        current = current.transition(SupervisorState.CLEANUP)

                    current = current.mark_cleanup_complete()
                    self._executions[execution_id] = current

            if cleanup_error is not None:
                raise cleanup_error

            raise

    def execute_worker(
        self,
        execution_id: UUID,
        payload: dict[str, Any],
        *,
        timeout_seconds: float | None = None,
    ) -> WorkerMessage:
        execution = self._get(execution_id)
        worker = self._workers.get(execution_id)

        if worker is None:
            raise SupervisorInvariantError(
                "no worker registered for execution"
            )

        if execution.state != SupervisorState.READY:
            raise SupervisorInvariantError(
                "worker execution requires READY state"
            )

        self.transition(execution_id, SupervisorState.RUNNING)

        try:
            result = worker.execute(
                payload,
                timeout_seconds=(
                    timeout_seconds
                    if timeout_seconds is not None
                    else execution.policy.timeout_seconds
                ),
            )

            self.transition(execution_id, SupervisorState.COMPLETED)
            return result

        except TimeoutError:
            self.transition(execution_id, SupervisorState.TIMING_OUT)

            current = self._get(execution_id)

            try:
                if (
                    self._enforcement_adapter is not None
                    and current.prepared_enforcement is not None
                ):
                    self._enforcement_adapter.terminate(
                        current.prepared_enforcement,
                        exit_code=124,
                    )
            finally:
                worker.terminate()

            raise

        except BaseException:
            self.transition(execution_id, SupervisorState.CRASHED)
            raise

    def _release_enforcement(self, execution_id: UUID) -> None:
        execution = self._get(execution_id)
        prepared = execution.prepared_enforcement

        if prepared is None:
            return

        self._executions[execution_id] = replace(
            execution,
            prepared_enforcement=None,
        )

        if self._enforcement_adapter is not None:
            self._enforcement_adapter.release(prepared)

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

        worker = self._workers.get(execution_id)

        if worker is not None:
            try:
                worker.terminate()
            finally:
                worker.close()

        self._release_enforcement(execution_id)

        execution = self._get(execution_id)

        if execution.state != SupervisorState.CLEANUP:
            execution = execution.transition(SupervisorState.CLEANUP)

        updated = execution.mark_cleanup_complete()
        self._executions[execution_id] = updated
        self._workers.pop(execution_id, None)

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
