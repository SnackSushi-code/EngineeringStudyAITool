from __future__ import annotations

from typing import Protocol

from .cancellation import CancellationToken
from .contracts import TaskRequest, ToolCall
from .intelligence_contracts import IntelligenceDecisionType
from .intelligence_orchestrator import IntelligenceInvocation
from .orchestrator import TaskOrchestrator, TaskOutcome


class IntelligenceRuntimeBridgeError(RuntimeError):
    """Raised when an intelligence proposal cannot enter the runtime boundary."""


class TaskOrchestratorPort(Protocol):
    def run(
        self,
        request: TaskRequest,
        call: ToolCall,
        cancellation: CancellationToken | None = None,
    ) -> TaskOutcome:
        ...


class IntelligenceRuntimeBridge:
    """Controlled bridge from intelligence proposals to the existing runtime.

    The bridge accepts an already validated IntelligenceInvocation and an
    externally constructed TaskRequest. It never constructs permissions,
    changes policy, calls ToolExecutor, or executes handlers directly.
    """

    def __init__(self, task_orchestrator: TaskOrchestratorPort, authority_resolver: ToolAuthorityResolver) -> None:
        self._task_orchestrator = task_orchestrator
        self._authority_resolver = authority_resolver

    def execute_proposal(
        self,
        invocation: IntelligenceInvocation,
        task_request: TaskRequest,
        cancellation: CancellationToken | None = None,
    ) -> TaskOutcome:
        if not isinstance(invocation, IntelligenceInvocation):
            raise IntelligenceRuntimeBridgeError(
                "invocation must be an IntelligenceInvocation"
            )

        decision = invocation.result.decision
        if decision.decision_type != IntelligenceDecisionType.TOOL_PROPOSAL:
            raise IntelligenceRuntimeBridgeError(
                "only TOOL_PROPOSAL decisions can enter the runtime bridge"
            )

        proposal = decision.tool_call
        if proposal is None:
            raise IntelligenceRuntimeBridgeError(
                "TOOL_PROPOSAL is missing its tool proposal"
            )

        if task_request.request_id != invocation.result.request.request_id:
            raise IntelligenceRuntimeBridgeError(
                "TaskRequest request_id does not match IntelligenceRequest"
            )

        if task_request.task_id != invocation.result.request.task_id:
            raise IntelligenceRuntimeBridgeError(
                "TaskRequest task_id does not match IntelligenceRequest"
            )

        if proposal.request_id != task_request.request_id:
            raise IntelligenceRuntimeBridgeError(
                "tool proposal request_id does not match TaskRequest"
            )

        if proposal.task_id != task_request.task_id:
            raise IntelligenceRuntimeBridgeError(
                "tool proposal task_id does not match TaskRequest"
            )

        resolved = self._authority_resolver.resolve(proposal)
        return self._task_orchestrator.run(task_request, resolved.call, cancellation)
