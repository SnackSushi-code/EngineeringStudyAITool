from __future__ import annotations

from concurrent.futures import (
    Future,
    ThreadPoolExecutor,
    TimeoutError as FutureTimeoutError,
)
from threading import Lock
from time import monotonic
from typing import Any, Mapping

from .cancellation import CancellationRequested, CancellationToken
from .contracts import (
    PermissionDecision,
    PermissionRequest,
    RetryMode,
    TaskState,
    ToolCall,
    ToolResult,
)
from .policy import PolicyBroker
from .tool_contracts import (
    ResultValidator,
    ToolApprovalRequiredError,
    ToolAuditEvent,
    ToolExecutionContext,
    ToolInvocation,
)
from .tool_registry import ToolRegistry


class ToolExecutor:
    """Fail-closed execution boundary for registered tools."""

    def __init__(
        self,
        registry: ToolRegistry,
        policy: PolicyBroker,
        *,
        principal_type: str = "agent",
        principal_id: str = "runtime",
        validators: Mapping[str, ResultValidator] | None = None,
    ) -> None:
        self._registry = registry
        self._policy = policy
        self._principal_type = principal_type
        self._principal_id = principal_id
        self._validators = dict(validators or {})
        self._audit: list[ToolAuditEvent] = []
        self._audit_lock = Lock()

    @property
    def audit_events(self) -> tuple[ToolAuditEvent, ...]:
        with self._audit_lock:
            return tuple(self._audit)

    def execute(
        self,
        call: ToolCall,
        authorization: tuple[PermissionRequest, ...] | None = None,
        cancellation: CancellationToken | None = None,
    ) -> ToolResult:
        """
        Execute a runtime-generated ToolCall.

        The method accepts both:
            executor.execute(call)
        and the runtime interface:
            executor.execute(call, authorization, cancellation)
        """
        cancellation = cancellation or CancellationToken()

        try:
            cancellation.throw_if_requested()

            descriptor, handler = self._registry.get(call.tool)

        except KeyError:
            self._record(
                call,
                "unknown",
                "REJECTED",
                0,
                (),
                "UNKNOWN_TOOL",
            )
            return self._failure(
                call,
                "unknown",
                "UNKNOWN_TOOL",
                f"Unknown tool: {call.tool}",
            )

        try:
            ToolInvocation(
                call=call,
                descriptor=descriptor,
            )
        except Exception as exc:
            self._record(
                call,
                descriptor.version,
                "REJECTED",
                0,
                (),
                "INVALID_INVOCATION",
            )
            return self._failure(
                call,
                descriptor.version,
                "INVALID_INVOCATION",
                str(exc),
                details={
                    "exception_type": type(exc).__name__,
                },
            )

        expected_authorization = (
            self._build_runtime_authorization_requests(call)
        )

        supplied_authorization = (
            tuple(authorization)
            if authorization is not None
            else expected_authorization
        )

        if supplied_authorization != expected_authorization:
            self._record(
                call,
                descriptor.version,
                "REJECTED",
                0,
                (),
                "AUTHORIZATION_MISMATCH",
            )
            return self._failure(
                call,
                descriptor.version,
                "AUTHORIZATION_MISMATCH",
                "Supplied authorization does not match runtime-derived authority.",
            )

        authorization_records: list[Mapping[str, Any]] = []

        for permission_request in expected_authorization:
            decision = self._policy.evaluate(permission_request)

            authorization_records.append(
                {
                    "permission_class": (
                        permission_request.permission_class.value
                    ),
                    "target": permission_request.target,
                    "decision": decision.decision.value,
                    "policy_version": decision.policy_version,
                    "approval_id": (
                        str(decision.approval_id)
                        if decision.approval_id
                        else None
                    ),
                }
            )

            if decision.decision == PermissionDecision.REQUIRE_APPROVAL:
                self._record(
                    call,
                    descriptor.version,
                    "APPROVAL_REQUIRED",
                    0,
                    tuple(authorization_records),
                    "APPROVAL_REQUIRED",
                )

                raise ToolApprovalRequiredError(
                    decision,
                    permission_request.permission_class.value,
                    permission_request.target,
                )

            if decision.decision == PermissionDecision.DENY:
                self._record(
                    call,
                    descriptor.version,
                    "DENIED",
                    0,
                    tuple(authorization_records),
                    "PERMISSION_DENIED",
                )

                return self._failure(
                    call,
                    descriptor.version,
                    "PERMISSION_DENIED",
                    (
                        "Tool permission was denied: "
                        f"{permission_request.permission_class.value} "
                        f"{permission_request.target}"
                    ),
                    status=TaskState.DENIED,
                )

            if decision.decision != PermissionDecision.ALLOW:
                raise AssertionError(
                    "Unhandled permission decision: "
                    f"{decision.decision!r}"
                )

        # The descriptor and ToolCall both carry retry policy.
        # The existing contract has no max_retries field, so SAFE retry
        # means exactly one retry: two total attempts.
        retry_allowed = (
            descriptor.retry_mode == RetryMode.SAFE
            and call.retry_mode == RetryMode.SAFE
        )
        max_attempts = 2 if retry_allowed else 1

        validator = self._validators.get(descriptor.tool_id)

        for attempt in range(1, max_attempts + 1):
            cancellation.throw_if_requested()

            context = ToolExecutionContext(
                request_id=call.request_id,
                task_id=call.task_id,
                tool_id=descriptor.tool_id,
                tool_version=descriptor.version,
                attempt=attempt,
            )

            self._record(
                call,
                descriptor.version,
                "AUTHORIZED_EXECUTION",
                attempt,
                tuple(authorization_records),
                None,
            )

            try:
                result = self._run_handler(
                    handler=handler,
                    context=context,
                    arguments=call.arguments,
                    timeout_ms=call.timeout_ms,
                    cancellation=cancellation,
                )

                cancellation.throw_if_requested()

                validation_checks: tuple[Mapping[str, Any], ...]

                if validator is None:
                    validation_state = "NOT_APPLICABLE"
                    validation_checks = ()
                else:
                    valid, validation_checks = validator.validate(result)

                    validation_state = (
                        "PASSED"
                        if valid
                        else "FAILED"
                    )

                    if not valid:
                        self._record(
                            call,
                            descriptor.version,
                            "VALIDATION_FAILED",
                            attempt,
                            tuple(authorization_records),
                            "RESULT_VALIDATION_FAILED",
                        )

                        return self._failure(
                            call,
                            descriptor.version,
                            "RESULT_VALIDATION_FAILED",
                            "Tool result failed validation.",
                            validation_checks=validation_checks,
                        )

                self._record(
                    call,
                    descriptor.version,
                    "SUCCEEDED",
                    attempt,
                    tuple(authorization_records),
                    None,
                )

                return ToolResult(
                    schema_version="1.0",
                    request_id=call.request_id,
                    task_id=call.task_id,
                    status=TaskState.SUCCEEDED,
                    result=dict(result),
                    artifacts=(),
                    validation_state=validation_state,
                    validation_checks=validation_checks,
                    tool=descriptor.tool_id,
                    tool_version=descriptor.version,
                    adapter_version="tool-executor-1.0",
                    error=None,
                    logs=(
                        f"tool={descriptor.tool_id}",
                        f"attempt={attempt}",
                    ),
                )

            except CancellationRequested:
                if cancellation.reason == "execution timeout":
                    self._record(
                        call,
                        descriptor.version,
                        "TIMED_OUT",
                        attempt,
                        tuple(authorization_records),
                        "TIMEOUT",
                    )
                else:
                    self._record(
                        call,
                        descriptor.version,
                        "CANCELLED",
                        attempt,
                        tuple(authorization_records),
                        "CANCELLED",
                    )

                raise

            except TimeoutError:
                self._record(
                    call,
                    descriptor.version,
                    "TIMED_OUT",
                    attempt,
                    tuple(authorization_records),
                    "TIMEOUT",
                )

                return self._failure(
                    call,
                    descriptor.version,
                    "TIMEOUT",
                    "Tool execution exceeded its timeout.",
                    status=TaskState.TIMED_OUT,
                )

            except Exception as exc:
                if attempt < max_attempts:
                    self._record(
                        call,
                        descriptor.version,
                        "RETRYING",
                        attempt,
                        tuple(authorization_records),
                        type(exc).__name__,
                    )
                    continue

                self._record(
                    call,
                    descriptor.version,
                    "FAILED",
                    attempt,
                    tuple(authorization_records),
                    type(exc).__name__,
                )

                return self._failure(
                    call,
                    descriptor.version,
                    type(exc).__name__,
                    str(exc),
                    details={
                        "exception_type": type(exc).__name__,
                    },
                )

        raise AssertionError("Unreachable tool execution state.")

    def _build_runtime_authorization_requests(
        self,
        call: ToolCall,
    ) -> tuple[PermissionRequest, ...]:
        """
        Reconstruct authorization from the registered descriptor.

        The model-provided ToolCall permissions are never treated as the
        authority source. They are checked by ToolInvocation and then the
        runtime independently derives the expected permission requests.
        """
        try:
            descriptor, _ = self._registry.get(call.tool)
        except KeyError:
            return ()

        return tuple(
            PermissionRequest(
                schema_version=call.schema_version,
                request_id=call.request_id,
                principal_type=self._principal_type,
                principal_id=self._principal_id,
                permission_class=permission.permission_class,
                target=permission.scope,
                reason=f"Tool operation {call.tool}.{call.operation}",
                task_id=call.task_id,
            )
            for permission in descriptor.required_permissions
        )

    @staticmethod
    def _run_handler(
        handler: Any,
        context: ToolExecutionContext,
        arguments: Mapping[str, Any],
        timeout_ms: int,
        cancellation: CancellationToken,
    ) -> Mapping[str, Any]:
        """
        Execute a handler with a real wall-clock deadline.

        A Python worker thread cannot be safely force-killed. Once the
        deadline expires, the runtime signals cooperative cancellation,
        cancels pending work, stops waiting for the worker, and reports the
        timeout without blocking on worker completion.
        """
        cancellation.throw_if_requested()

        if timeout_ms <= 0:
            raise ValueError("Tool timeout must be positive.")

        executor = ThreadPoolExecutor(max_workers=1)

        future: Future[Mapping[str, Any]] = executor.submit(
            handler,
            context,
            arguments,
        )

        deadline = monotonic() + (timeout_ms / 1000.0)

        try:
            while True:
                cancellation.throw_if_requested()

                remaining = deadline - monotonic()

                if remaining <= 0:
                    context.cancellation_event.set()
                    future.cancel()

                    executor.shutdown(
                        wait=False,
                        cancel_futures=True,
                    )

                    raise TimeoutError(
                        "Tool execution exceeded its timeout."
                    )

                try:
                    result = future.result(
                        timeout=min(0.05, remaining)
                    )
                    break

                except FutureTimeoutError:
                    continue

        except CancellationRequested:
            context.cancellation_event.set()
            future.cancel()

            executor.shutdown(
                wait=False,
                cancel_futures=True,
            )
            raise

        except TimeoutError:
            context.cancellation_event.set()
            future.cancel()

            executor.shutdown(
                wait=False,
                cancel_futures=True,
            )
            raise

        except BaseException:
            context.cancellation_event.set()
            future.cancel()

            executor.shutdown(
                wait=False,
                cancel_futures=True,
            )
            raise

        else:
            executor.shutdown(wait=True)

        if not isinstance(result, Mapping):
            raise TypeError(
                "Tool handler must return a mapping."
            )

        return result

    def _record(
        self,
        call: ToolCall,
        version: str,
        status: str,
        attempt: int,
        authorization: tuple[Mapping[str, Any], ...],
        error_code: str | None,
    ) -> None:
        with self._audit_lock:
            self._audit.append(
                ToolAuditEvent(
                    request_id=call.request_id,
                    task_id=call.task_id,
                    tool_id=call.tool,
                    tool_version=version,
                    operation=call.operation,
                    status=status,
                    attempt=attempt,
                    authorization=authorization,
                    error_code=error_code,
                )
            )


    @staticmethod
    def _failure(
        call: ToolCall,
        version: str,
        code: str,
        message: str,
        *,
        status: TaskState = TaskState.FAILED,
        validation_checks: tuple[Mapping[str, Any], ...] = (),
        details: Mapping[str, Any] | None = None,
    ) -> ToolResult:
        return ToolResult(
            schema_version="1.0",
            request_id=call.request_id,
            task_id=call.task_id,
            status=status,
            result={},
            artifacts=(),
            validation_state="NOT_APPLICABLE",
            validation_checks=validation_checks,
            tool=call.tool,
            tool_version=version,
            adapter_version="tool-executor-1.0",
            error={
                "code": code,
                "message": message,
                "retryable": False,
                "request_id": str(call.request_id),
                "task_id": str(call.task_id),
                "details": dict(details or {}),
                "recovery": None,
            },
            logs=(),
        )
