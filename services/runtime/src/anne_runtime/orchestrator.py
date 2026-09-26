from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Thread
from time import monotonic
from uuid import UUID

from .audit import AppendOnlyAuditLog, AuditEvent
from .cancellation import CancellationRequested, CancellationToken
from .contracts import TaskRequest, TaskState, ToolCall, ToolResult
from .errors import ContractValidationError, PermissionDeniedError, RuntimeErrorInfo
from .execution import ExecutionCoordinator
from .lifecycle import LifecycleEvent, TaskLifecycle
from .retry import RetryPolicy, run_with_retry
from .schema_validation import validate_against_schema


@dataclass(frozen=True)
class TaskOutcome:
    request_id: UUID
    task_id: UUID
    state: TaskState
    result: ToolResult | None
    error: RuntimeErrorInfo | None
    lifecycle: tuple[LifecycleEvent, ...]


class TaskOrchestrator:
    """Owns task lifecycle and enforces the runtime execution pipeline."""

    def __init__(
        self,
        execution: ExecutionCoordinator,
        audit: AppendOnlyAuditLog,
        schema_dir,
        *,
        default_timeout_ms: int = 30_000,
    ) -> None:
        if default_timeout_ms <= 0:
            raise ValueError("default_timeout_ms must be positive")

        self._execution = execution
        self._audit = audit
        self._schema_dir = schema_dir
        self._default_timeout_ms = default_timeout_ms

    def run(
        self,
        request: TaskRequest,
        call: ToolCall,
        cancellation: CancellationToken | None = None,
    ) -> TaskOutcome:
        self._validate_request_and_correlation(request, call)

        lifecycle = TaskLifecycle(
            request.request_id,
            request.task_id,
        )

        cancellation = cancellation or CancellationToken()

        try:
            lifecycle.transition(TaskState.PLANNING)

            self._validate_tool_call(call)

            # Policy authorization is a pre-execution gate. The task does not
            # enter RUNNING until the controlled execution path has confirmed
            # that every declared permission is authorized.
            try:
                authorization = self._execution.preflight(
                    call,
                    cancellation,
                )

            except CancellationRequested as exc:
                lifecycle.transition(
                    TaskState.CANCELLED,
                    str(exc),
                )

                error = self._error(
                    "ANN_E_TASK_CANCELLED",
                    str(exc),
                    False,
                    request,
                )

                self._audit_task(
                    request,
                    "CANCELLED",
                    error.message,
                )

                return self._outcome(
                    lifecycle,
                    result=None,
                    error=error,
                )

            except PermissionDeniedError as exc:
                lifecycle.transition(
                    TaskState.DENIED,
                    str(exc),
                )

                error = self._error(
                    "ANN_E_PERMISSION_DENIED",
                    "Operation denied by policy.",
                    False,
                    request,
                )

                self._audit_task(
                    request,
                    "DENIED",
                    str(exc),
                )

                return self._outcome(
                    lifecycle,
                    result=None,
                    error=error,
                )

            lifecycle.transition(TaskState.RUNNING)

            timeout_ms = call.timeout_ms or self._default_timeout_ms

            if timeout_ms <= 0:
                raise ContractValidationError(
                    "timeout_ms must be positive"
                )

            retry_policy = RetryPolicy(
                mode=call.retry_mode,
                max_attempts=(
                    2
                    if call.retry_mode.value == "safe"
                    else 1
                ),
            )

            timeout_fired = Event()
            watchdog_stop = Event()

            def watchdog() -> None:
                if watchdog_stop.wait(timeout_ms / 1000):
                    return

                if not cancellation.is_requested:
                    timeout_fired.set()
                    cancellation.request("execution timeout")

            watchdog_thread = Thread(
                target=watchdog,
                name=f"anne-timeout-{request.task_id}",
                daemon=True,
            )

            watchdog_thread.start()

            def execute_once() -> ToolResult:
                cancellation.throw_if_requested()

                return self._execution.execute(
                    call,
                    cancellation,
                    authorization,
                )

            try:
                result = run_with_retry(
                    execute_once,
                    retry_policy,
                    is_retryable=lambda exc: isinstance(
                        exc,
                        TimeoutError,
                    ),
                )

            except CancellationRequested as exc:
                if timeout_fired.is_set():
                    lifecycle.transition(
                        TaskState.TIMED_OUT,
                        str(exc),
                    )

                    error = self._error(
                        "ANN_E_TASK_TIMED_OUT",
                        "Task exceeded its execution timeout.",
                        True,
                        request,
                    )

                    self._audit_task(
                        request,
                        "TIMED_OUT",
                        str(exc),
                    )

                    return self._outcome(
                        lifecycle,
                        result=None,
                        error=error,
                    )

                lifecycle.transition(
                    TaskState.CANCELLED,
                    str(exc),
                )

                error = self._error(
                    "ANN_E_TASK_CANCELLED",
                    str(exc),
                    False,
                    request,
                )

                self._audit_task(
                    request,
                    "CANCELLED",
                    error.message,
                )

                return self._outcome(
                    lifecycle,
                    result=None,
                    error=error,
                )

            except PermissionDeniedError as exc:
                lifecycle.transition(
                    TaskState.DENIED,
                    str(exc),
                )

                error = self._error(
                    "ANN_E_PERMISSION_DENIED",
                    "Operation denied by policy.",
                    False,
                    request,
                )

                self._audit_task(
                    request,
                    "DENIED",
                    str(exc),
                )

                return self._outcome(
                    lifecycle,
                    result=None,
                    error=error,
                )

            except TimeoutError as exc:
                timeout_fired.set()
                cancellation.request("execution timeout")

                lifecycle.transition(
                    TaskState.TIMED_OUT,
                    str(exc),
                )

                error = self._error(
                    "ANN_E_TASK_TIMED_OUT",
                    "Task exceeded its execution timeout.",
                    True,
                    request,
                )

                self._audit_task(
                    request,
                    "TIMED_OUT",
                    str(exc),
                )

                return self._outcome(
                    lifecycle,
                    result=None,
                    error=error,
                )

            else:
                lifecycle.transition(TaskState.VALIDATING)

                self._validate_tool_result(
                    result,
                    call,
                )

                lifecycle.transition(result.status)

                # ToolExecutor may contain an execution timeout internally and
                # return a terminal TIMED_OUT ToolResult rather than raising.
                # Preserve that ToolResult while also exposing the task-level
                # RuntimeErrorInfo expected by TaskOutcome consumers.
                if result.status == TaskState.TIMED_OUT:
                    error = self._error(
                        "ANN_E_TASK_TIMED_OUT",
                        "Task exceeded its execution timeout.",
                        True,
                        request,
                    )

                    self._audit_task(
                        request,
                        "TIMED_OUT",
                        "tool execution timed out",
                    )

                    return self._outcome(
                        lifecycle,
                        result=result,
                        error=error,
                    )

                self._audit_task(
                    request,
                    result.status.value,
                    "tool execution completed",
                )

                return self._outcome(
                    lifecycle,
                    result=result,
                    error=None,
                )

            finally:
                # The watchdog belongs to this execution scope. Always stop
                # it before returning or propagating an execution exception so
                # a completed task cannot be mutated by a late timeout signal.
                watchdog_stop.set()
                watchdog_thread.join()

        except Exception as exc:
            if lifecycle.state not in {
                TaskState.SUCCEEDED,
                TaskState.FAILED,
                TaskState.CANCELLED,
                TaskState.DENIED,
                TaskState.TIMED_OUT,
            }:
                lifecycle.transition(
                    TaskState.FAILED,
                    str(exc),
                )

            error = self._error(
                "ANN_E_RUNTIME_FAILURE",
                "Task failed during runtime processing.",
                False,
                request,
                details={
                    "type": type(exc).__name__,
                },
            )

            self._audit_task(
                request,
                "FAILED",
                type(exc).__name__,
            )

            return self._outcome(
                lifecycle,
                result=None,
                error=error,
            )

    def cancel(
        self,
        cancellation: CancellationToken,
        reason: str = "user requested cancellation",
    ) -> None:
        cancellation.request(reason)

    def _validate_request_and_correlation(
        self,
        request: TaskRequest,
        call: ToolCall,
    ) -> None:
        if (
            request.request_id != call.request_id
            or request.task_id != call.task_id
        ):
            raise ContractValidationError(
                "TaskRequest and ToolCall correlation IDs must match"
            )

        validate_against_schema(
            request.to_dict(),
            "task-request.schema.json",
            self._schema_dir,
        )

    def _validate_tool_call(
        self,
        call: ToolCall,
    ) -> None:
        validate_against_schema(
            call.to_dict(),
            "tool-call.schema.json",
            self._schema_dir,
        )

        if not call.permissions:
            raise ContractValidationError(
                "ToolCall must declare at least one permission scope"
            )

        if (
            call.retry_mode.value == "safe"
            and not call.idempotency_key
        ):
            raise ContractValidationError(
                "SAFE retry requires an idempotency key"
            )

    def _validate_tool_result(
        self,
        result: ToolResult,
        call: ToolCall,
    ) -> None:
        validate_against_schema(
            result.to_dict(),
            "tool-result.schema.json",
            self._schema_dir,
        )

        if (
            result.request_id != call.request_id
            or result.task_id != call.task_id
        ):
            raise ContractValidationError(
                "ToolResult correlation IDs must match ToolCall"
            )

    def _audit_task(
        self,
        request: TaskRequest,
        outcome: str,
        detail: str,
    ) -> None:
        self._audit.append(
            AuditEvent(
                request_id=str(request.request_id),
                task_id=str(request.task_id),
                principal=request.source,
                operation="task.execute",
                policy_decision="ROUTED_THROUGH_BROKER",
                target=str(request.workspace_id),
                outcome=outcome,
                details={
                    "detail": detail,
                },
            )
        )

    @staticmethod
    def _error(
        code: str,
        message: str,
        retryable: bool,
        request: TaskRequest,
        details=None,
    ) -> RuntimeErrorInfo:
        return RuntimeErrorInfo(
            code,
            message,
            retryable,
            str(request.request_id),
            str(request.task_id),
            details or {},
        )

    @staticmethod
    def _outcome(
        lifecycle: TaskLifecycle,
        result: ToolResult | None,
        error: RuntimeErrorInfo | None,
    ) -> TaskOutcome:
        return TaskOutcome(
            lifecycle.request_id,
            lifecycle.task_id,
            lifecycle.state,
            result,
            error,
            lifecycle.events(),
        )
