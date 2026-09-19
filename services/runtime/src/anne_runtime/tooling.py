from __future__ import annotations

from abc import ABC, abstractmethod

from .contracts import (
    PermissionRequest,
    ToolCall,
    ToolResult,
)
from .errors import PermissionDeniedError
from .policy import PolicyBroker


class ToolExecutor(ABC):
    """Execution boundary. Implementations must not broaden authorized scope."""

    @abstractmethod
    def execute(
        self,
        call: ToolCall,
        authorization: tuple[PermissionRequest, ...],
    ) -> ToolResult:
        raise NotImplementedError


class NoopToolExecutor(ToolExecutor):
    """Safe integration-test executor; performs no external operation."""

    def execute(
        self,
        call: ToolCall,
        authorization: tuple[PermissionRequest, ...],
    ) -> ToolResult:
        from .contracts import TaskState

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
            adapter_version="0.4.1",
            error=None,
            logs=(),
        )


class AuthorizedToolRunner:
    """Combines policy decisions with the execution boundary."""

    def __init__(self, broker: PolicyBroker, executor: ToolExecutor):
        self.broker = broker
        self.executor = executor

    def run(self, call: ToolCall) -> ToolResult:
        requests = tuple(
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

        decisions = tuple(
            self.broker.evaluate(request)
            for request in requests
        )

        if any(
            decision.decision.value != "ALLOW"
            for decision in decisions
        ):
            raise PermissionDeniedError(
                "Tool call does not have complete authorization"
            )

        return self.executor.execute(call, requests)
