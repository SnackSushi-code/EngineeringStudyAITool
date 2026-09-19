from __future__ import annotations

from abc import ABC, abstractmethod

from .cancellation import CancellationToken
from .contracts import PermissionRequest, ToolCall, ToolResult
from .errors import PermissionDeniedError
from .policy import PolicyBroker


class ToolExecutor(ABC):
    """Execution boundary. Implementations must honor cancellation and scope."""

    @abstractmethod
    def execute(
        self,
        call: ToolCall,
        authorization: tuple[PermissionRequest, ...],
        cancellation: CancellationToken,
    ) -> ToolResult:
        raise NotImplementedError


class NoopToolExecutor(ToolExecutor):
    """Safe integration-test executor; performs no external operation."""

    def execute(self, call, authorization, cancellation):
        from .contracts import TaskState
        cancellation.throw_if_requested()
        return ToolResult(
            schema_version=call.schema_version,
            request_id=call.request_id,
            task_id=call.task_id,
            status=TaskState.SUCCEEDED,
            result={"executed": False, "reason": "noop_executor"},
            artifacts=(),
            validation_state="NOT_APPLICABLE",
            validation_checks=(),
            tool=call.tool,
            tool_version="noop",
            adapter_version="0.4.2",
            error=None,
            logs=(),
        )


class AuthorizedToolRunner:
    """The only runtime bridge from a ToolCall to a ToolExecutor."""

    def __init__(self, broker: PolicyBroker, executor: ToolExecutor):
        self.broker = broker
        self.executor = executor

    def _requests(self, call: ToolCall) -> tuple[PermissionRequest, ...]:
        return tuple(
            PermissionRequest(
                schema_version=call.schema_version,
                request_id=call.request_id,
                principal_type="agent",
                principal_id="runtime",
                permission_class=permission.permission_class,
                target=permission.scope,
                reason=f"Tool operation {call.tool}.{call.operation}",
                task_id=call.task_id,
            )
            for permission in call.permissions
        )

    def authorize(self, call: ToolCall, cancellation: CancellationToken | None = None) -> tuple[PermissionRequest, ...]:
        cancellation = cancellation or CancellationToken()
        cancellation.throw_if_requested()
        requests = self._requests(call)
        decisions = tuple(self.broker.evaluate(request) for request in requests)
        if any(decision.decision.value != "ALLOW" for decision in decisions):
            raise PermissionDeniedError("Tool call does not have complete authorization")
        return requests

    def run(
        self,
        call: ToolCall,
        cancellation: CancellationToken | None = None,
        authorization: tuple[PermissionRequest, ...] | None = None,
    ) -> ToolResult:
        cancellation = cancellation or CancellationToken()
        requests = authorization if authorization is not None else self.authorize(call, cancellation)
        cancellation.throw_if_requested()
        return self.executor.execute(call, requests, cancellation)
