from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from threading import Lock
from typing import Any, Mapping

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
        principal_type: str = "system",
        principal_id: str = "anne-runtime",
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

    def execute(self, call: ToolCall) -> ToolResult:
        try:
            descriptor, handler = self._registry.get(call.tool)
        except KeyError:
            self._record(call, "unknown", "REJECTED", 0, (), "UNKNOWN_TOOL")
            return self._failure(call, "unknown", "UNKNOWN_TOOL", f"Unknown tool: {call.tool}")

        try:
            ToolInvocation(call=call, descriptor=descriptor)
        except Exception as exc:
            self._record(call, descriptor.version, "REJECTED", 0, (), "INVALID_INVOCATION")
            return self._failure(call, descriptor.version, "INVALID_INVOCATION", str(exc))

        authorization: list[Mapping[str, Any]] = []

        for permission in descriptor.required_permissions:
            request = PermissionRequest(
                schema_version="1.0",
                request_id=call.request_id,
                principal_type=self._principal_type,
                principal_id=self._principal_id,
                permission_class=permission.permission_class,
                target=permission.scope,
                reason=f"Tool invocation: {call.tool}.{call.operation}",
                task_id=call.task_id,
            )
            decision = self._policy.evaluate(request)
            authorization.append({
                "permission_class": permission.permission_class.value,
                "target": permission.scope,
                "decision": decision.decision.value,
                "policy_version": decision.policy_version,
                "approval_id": str(decision.approval_id) if decision.approval_id else None,
            })
            if decision.decision == PermissionDecision.REQUIRE_APPROVAL:
                self._record(
                    call,
                    descriptor.version,
                    "APPROVAL_REQUIRED",
                    0,
                    tuple(authorization),
                    "APPROVAL_REQUIRED",
                )
                raise ToolApprovalRequiredError(
                    decision,
                    permission.permission_class.value,
                    permission.scope,
                )

            if decision.decision == PermissionDecision.ALLOW:
                continue

            if decision.decision == PermissionDecision.DENY:
                self._record(
                    call,
                    descriptor.version,
                    "DENIED",
                    0,
                    tuple(authorization),
                    "PERMISSION_DENIED",
                )
                return self._failure(
                    call,
                    descriptor.version,
                    "PERMISSION_DENIED",
                    f"Tool permission was denied: "
                    f"{permission.permission_class.value} "
                    f"{permission.scope}",
                    status=TaskState.DENIED,
                )

            raise AssertionError(
                f"Unhandled permission decision: {decision.decision!r}"
            )

        retry_allowed = (
            descriptor.retry_mode == RetryMode.SAFE
            and call.retry_mode == RetryMode.SAFE
        )
        max_attempts = 2 if retry_allowed else 1

        for attempt in range(1, max_attempts + 1):
            context = ToolExecutionContext(
                request_id=call.request_id,
                task_id=call.task_id,
                tool_id=descriptor.tool_id,
                tool_version=descriptor.version,
                attempt=attempt,
            )
            self._record(
                call, descriptor.version, "AUTHORIZED_EXECUTION", attempt,
                tuple(authorization), None
            )
            try:
                result = self._run_handler(
                    handler, context, call.arguments, call.timeout_ms
                )

                validator = self._validators.get(descriptor.tool_id)
                if validator is None:
                    validation_state = "NOT_VALIDATED"
                    validation_checks = ()
                else:
                    valid, validation_checks = validator.validate(result)
                    validation_state = "PASSED" if valid else "FAILED"
                    if not valid:
                        self._record(
                            call, descriptor.version, "VALIDATION_FAILED",
                            attempt, tuple(authorization),
                            "RESULT_VALIDATION_FAILED"
                        )
                        return self._failure(
                            call, descriptor.version,
                            "RESULT_VALIDATION_FAILED",
                            "Tool result failed validation.",
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
                    logs=(f"tool={descriptor.tool_id}", f"attempt={attempt}"),
                )

            except FutureTimeoutError:
                context.cancellation_event.set()
                self._record(
                    call, descriptor.version, "TIMED_OUT", attempt,
                    tuple(authorization), "TIMEOUT"
                )
                return self._failure(
                    call, descriptor.version, "TIMEOUT",
                    "Tool execution exceeded its timeout.",
                    status=TaskState.TIMED_OUT,
                )

            except Exception as exc:
                if attempt < max_attempts:
                    self._record(
                        call, descriptor.version, "RETRYING", attempt,
                        tuple(authorization), type(exc).__name__
                    )
                    continue
                self._record(
                    call, descriptor.version, "FAILED", attempt,
                    tuple(authorization), type(exc).__name__
                )
                return self._failure(
                    call, descriptor.version, type(exc).__name__, str(exc)
                )

        raise AssertionError("Unreachable tool execution state.")

    @staticmethod
    def _run_handler(
        handler: Any,
        context: ToolExecutionContext,
        arguments: Mapping[str, Any],
        timeout_ms: int,
    ) -> Mapping[str, Any]:
        executor = ThreadPoolExecutor(max_workers=1)
        future: Future[Mapping[str, Any]] = executor.submit(
            handler, context, arguments
        )
        try:
            result = future.result(timeout=timeout_ms / 1000.0)
        except FutureTimeoutError:
            context.cancellation_event.set()
            future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            raise
        except BaseException:
            executor.shutdown(wait=False, cancel_futures=True)
            raise
        else:
            executor.shutdown(wait=True)

        if not isinstance(result, Mapping):
            raise TypeError("Tool handler must return a mapping.")
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
    ) -> ToolResult:
        return ToolResult(
            schema_version="1.0",
            request_id=call.request_id,
            task_id=call.task_id,
            status=status,
            result={},
            artifacts=(),
            validation_state="NOT_VALIDATED",
            validation_checks=(),
            tool=call.tool,
            tool_version=version,
            adapter_version="tool-executor-1.0",
            error={"code": code, "message": message},
            logs=(),
        )
