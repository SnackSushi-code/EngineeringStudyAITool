from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from uuid import UUID

from .execution_supervisor import ExecutionSupervisor, SupervisorExecution, SupervisorInvariantError, SupervisorState
from .isolation import IsolationPolicy, WorkerDescriptor
from .observability import RuntimeTelemetry
from .worker_process import WorkerProcess, WorkerProcessError, WorkerProcessState
from .worker_protocol import WorkerMessage, WorkerMessageType
from .contracts import ToolCall


@dataclass(frozen=True)
class SupervisedExecutionResult:
    execution_id: UUID
    state: SupervisorState
    response: WorkerMessage | None
    error_code: str | None = None
    error_message: str | None = None


WorkerHandler = Callable[[WorkerMessage], dict[str, Any]]


class SupervisedExecution:
    """Connects ExecutionSupervisor lifecycle authority to WorkerProcess.

    This layer owns the orchestration between authorization, worker startup,
    execution, timeout/cancellation recovery, and cleanup. It does not claim
    OS-level sandbox enforcement.
    """

    def __init__(
        self,
        supervisor: ExecutionSupervisor,
        *,
        telemetry: RuntimeTelemetry | None = None,
    ) -> None:
        self._supervisor = supervisor
        self._telemetry = telemetry
        self._workers: dict[UUID, WorkerProcess] = {}

    def execute(
        self,
        call: ToolCall,
        worker: WorkerDescriptor,
        policy: IsolationPolicy,
        authorization: Any,
        handler: WorkerHandler,
    ) -> SupervisedExecutionResult:
        execution = self._supervisor.authorize(call, worker, policy, authorization)
        self._emit("worker_execution_authorized", execution)
        process = WorkerProcess(
            worker_id=worker.worker_id,
            handler=handler,
            max_message_bytes=policy.max_message_bytes,
        )
        self._workers[execution.execution_id] = process

        try:
            self._supervisor.transition(execution.execution_id, SupervisorState.STARTING)
            self._emit("worker_starting", execution)
            start = self._supervisor.build_start_message(execution.execution_id)
            ready = process.start(start, timeout_seconds=policy.timeout_seconds)
            self._supervisor.validate_worker_message(execution.execution_id, ready, expected_sequence=0)
            self._supervisor.transition(execution.execution_id, SupervisorState.READY)
            self._emit("worker_ready", execution)

            self._supervisor.transition(execution.execution_id, SupervisorState.RUNNING)
            self._emit("worker_running", execution)
            response = process.execute(dict(call.arguments), timeout_seconds=policy.timeout_seconds)
            self._supervisor.validate_worker_message(execution.execution_id, response, expected_sequence=1)
            if response.message_type != WorkerMessageType.RESULT:
                raise WorkerProcessError("worker returned a non-result response")

            self._supervisor.transition(execution.execution_id, SupervisorState.COMPLETED)
            self._emit("worker_completed", execution)
            return self._finish(execution.execution_id, response=response)

        except TimeoutError:
            return self._recover_terminal(
                execution.execution_id,
                process,
                state=SupervisorState.TIMING_OUT,
                code="WORKER_TIMEOUT",
                message="worker execution timed out",
            )
        except (WorkerProcessError, SupervisorInvariantError, ValueError) as exc:
            current = self._supervisor.get(execution.execution_id)
            if current.state not in {SupervisorState.CLEANUP, SupervisorState.TERMINAL}:
                if process.state == WorkerProcessState.CRASHED or not process.snapshot().pid:
                    try:
                        self._supervisor.transition(execution.execution_id, SupervisorState.CRASHED)
                    except SupervisorInvariantError:
                        pass
                else:
                    try:
                        self._supervisor.transition(execution.execution_id, SupervisorState.TERMINATING)
                    except SupervisorInvariantError:
                        pass
            self._emit("worker_failed", execution, fields={"error_type": type(exc).__name__})
            return self._finish_failure(execution.execution_id, process, "WORKER_EXECUTION_FAILED", "worker execution failed")
        except BaseException:
            self._emit("worker_failed", execution, fields={"error_type": "UnhandledException"})
            return self._finish_failure(execution.execution_id, process, "WORKER_EXECUTION_FAILED", "worker execution failed")

    def cancel(self, execution_id: UUID, *, timeout_seconds: float = 0.5) -> SupervisedExecutionResult:
        execution = self._supervisor.get(execution_id)
        process = self._workers[execution_id]
        if execution.state not in {SupervisorState.READY, SupervisorState.RUNNING}:
            raise SupervisorInvariantError("execution is not cancellable")

        self._supervisor.transition(execution_id, SupervisorState.CANCELLING)
        self._emit("worker_cancelling", execution)
        try:
            response = process.cancel(timeout_seconds=timeout_seconds)
            self._supervisor.transition(execution_id, SupervisorState.TERMINATING)
            self._emit("worker_termination_requested", execution)
            process.terminate(grace_seconds=timeout_seconds)
            return self._finish(execution_id, response=response)
        except (TimeoutError, WorkerProcessError):
            self._supervisor.transition(execution_id, SupervisorState.TERMINATING)
            process.terminate(grace_seconds=timeout_seconds)
            return self._finish_failure(execution_id, process, "WORKER_CANCELLED", "worker execution cancelled")

    def _recover_terminal(
        self,
        execution_id: UUID,
        process: WorkerProcess,
        *,
        state: SupervisorState,
        code: str,
        message: str,
    ) -> SupervisedExecutionResult:
        execution = self._supervisor.get(execution_id)
        if execution.state not in {state, SupervisorState.TERMINATING}:
            self._supervisor.transition(execution_id, state)
        self._emit("worker_recovery_started", execution, fields={"reason": code})
        if self._supervisor.get(execution_id).state != SupervisorState.TERMINATING:
            self._supervisor.transition(execution_id, SupervisorState.TERMINATING)
        process.terminate(grace_seconds=0.2)
        return self._finish_failure(execution_id, process, code, message)

    def _finish(self, execution_id: UUID, *, response: WorkerMessage | None) -> SupervisedExecutionResult:
        process = self._workers[execution_id]
        execution = self._supervisor.get(execution_id)
        if execution.state != SupervisorState.CLEANUP:
            self._supervisor.transition(execution_id, SupervisorState.CLEANUP)
        process.close()
        terminal = self._supervisor.cleanup(execution_id)
        self._workers.pop(execution_id, None)
        self._emit("worker_cleanup_complete", terminal)
        return SupervisedExecutionResult(terminal.execution_id, terminal.state, response)

    def _finish_failure(
        self,
        execution_id: UUID,
        process: WorkerProcess,
        code: str,
        message: str,
    ) -> SupervisedExecutionResult:
        execution = self._supervisor.get(execution_id)
        if execution.state not in {SupervisorState.CLEANUP, SupervisorState.TERMINAL}:
            try:
                self._supervisor.transition(execution_id, SupervisorState.CLEANUP)
            except SupervisorInvariantError:
                if execution.state != SupervisorState.TERMINATING:
                    raise
                self._supervisor.transition(execution_id, SupervisorState.CLEANUP)
        process.close()
        terminal = self._supervisor.cleanup(execution_id)
        self._workers.pop(execution_id, None)
        self._emit("worker_cleanup_complete", terminal, fields={"result_code": code})
        return SupervisedExecutionResult(terminal.execution_id, terminal.state, None, code, message)

    def _emit(self, name: str, execution: SupervisorExecution, *, fields: dict[str, Any] | None = None) -> None:
        if self._telemetry is not None:
            self._telemetry.emit(
                name,
                request_id=execution.request_id,
                task_id=execution.task_id,
                fields={"execution_id": str(execution.execution_id), **(fields or {})},
            )
