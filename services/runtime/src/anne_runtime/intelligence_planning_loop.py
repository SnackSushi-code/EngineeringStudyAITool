from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .cancellation import CancellationToken
from .contracts import TaskRequest, TaskState, ToolCall
from .intelligence_contracts import IntelligenceDecisionType, IntelligenceRequest
from .intelligence_orchestrator import IntelligenceInvocation, IntelligenceOrchestrator
from .intelligence_runtime_bridge import IntelligenceRuntimeBridge
from .orchestrator import TaskOutcome


class IntelligencePlanningError(RuntimeError):
    """Raised when the intelligence planning loop cannot proceed safely."""


@dataclass(frozen=True)
class PlanningIteration:
    """One model decision and, when applicable, its runtime outcome."""

    index: int
    invocation: IntelligenceInvocation
    task_outcome: TaskOutcome | None


@dataclass(frozen=True)
class IntelligencePlanningOutcome:
    """Terminal result of a bounded intelligence planning session."""

    final_response: str | None
    iterations: tuple[PlanningIteration, ...]
    last_task_outcome: TaskOutcome | None
    stop_reason: str

    @property
    def completed(self) -> bool:
        return self.final_response is not None


class IntelligencePlanningLoop:
    """Bounded planner/executor loop over the existing intelligence/runtime boundaries.

    The loop owns sequencing only. It does not authorize permissions, execute
    tools directly, or change runtime policy. Every tool proposal still crosses
    IntelligenceRuntimeBridge and TaskOrchestrator.
    """

    def __init__(
        self,
        intelligence: IntelligenceOrchestrator,
        runtime_bridge: IntelligenceRuntimeBridge,
        *,
        max_iterations: int = 8,
    ) -> None:
        if max_iterations <= 0:
            raise ValueError("max_iterations must be positive")

        self._intelligence = intelligence
        self._runtime_bridge = runtime_bridge
        self._max_iterations = max_iterations

    def run(
        self,
        request: IntelligenceRequest,
        task_request: TaskRequest,
        cancellation: CancellationToken | None = None,
    ) -> IntelligencePlanningOutcome:
        if not isinstance(request, IntelligenceRequest):
            raise IntelligencePlanningError(
                "request must be an IntelligenceRequest"
            )
        if not isinstance(task_request, TaskRequest):
            raise IntelligencePlanningError(
                "task_request must be a TaskRequest"
            )

        if request.request_id != task_request.request_id:
            raise IntelligencePlanningError(
                "TaskRequest request_id does not match IntelligenceRequest"
            )
        if request.task_id != task_request.task_id:
            raise IntelligencePlanningError(
                "TaskRequest task_id does not match IntelligenceRequest"
            )

        iterations: list[PlanningIteration] = []
        current_request = request
        last_outcome: TaskOutcome | None = None

        for index in range(1, self._max_iterations + 1):
            if cancellation is not None and cancellation.is_requested:
                return IntelligencePlanningOutcome(
                    final_response=None,
                    iterations=tuple(iterations),
                    last_task_outcome=last_outcome,
                    stop_reason="CANCELLED",
                )

            invocation = self._intelligence.process(current_request)
            decision = invocation.result.decision

            if decision.decision_type == IntelligenceDecisionType.FINAL_RESPONSE:
                return IntelligencePlanningOutcome(
                    final_response=decision.response_text,
                    iterations=tuple(
                        iterations
                        + [
                            PlanningIteration(
                                index=index,
                                invocation=invocation,
                                task_outcome=None,
                            )
                        ]
                    ),
                    last_task_outcome=last_outcome,
                    stop_reason="FINAL_RESPONSE",
                )

            if decision.decision_type != IntelligenceDecisionType.TOOL_PROPOSAL:
                raise IntelligencePlanningError(
                    f"unsupported decision type: {decision.decision_type}"
                )

            call = decision.tool_call
            if call is None:
                raise IntelligencePlanningError(
                    "TOOL_PROPOSAL is missing its ToolCall"
                )

            task_outcome = self._runtime_bridge.execute_proposal(
                invocation,
                task_request,
                cancellation,
            )

            iteration = PlanningIteration(
                index=index,
                invocation=invocation,
                task_outcome=task_outcome,
            )
            iterations.append(iteration)
            last_outcome = task_outcome

            if task_outcome.state != TaskState.SUCCEEDED:
                return IntelligencePlanningOutcome(
                    final_response=None,
                    iterations=tuple(iterations),
                    last_task_outcome=task_outcome,
                    stop_reason=f"TOOL_{task_outcome.state.value}",
                )

            if cancellation is not None and cancellation.is_requested:
                return IntelligencePlanningOutcome(
                    final_response=None,
                    iterations=tuple(iterations),
                    last_task_outcome=last_outcome,
                    stop_reason="CANCELLED",
                )

            current_request = self._request_after_tool(
                current_request,
                call,
                task_outcome,
            )

        return IntelligencePlanningOutcome(
            final_response=None,
            iterations=tuple(iterations),
            last_task_outcome=last_outcome,
            stop_reason="MAX_ITERATIONS",
        )

    @staticmethod
    def _request_after_tool(
        request: IntelligenceRequest,
        call: ToolCall,
        outcome: TaskOutcome,
    ) -> IntelligenceRequest:
        payload: dict[str, Any] = {
            "status": outcome.state.value,
            "tool": call.tool,
            "operation": call.operation,
        }

        if outcome.result is not None:
            payload["result"] = dict(outcome.result.result)
            payload["artifacts"] = list(outcome.result.artifacts)
            payload["validation"] = {
                "state": outcome.result.validation_state,
                "checks": [
                    dict(check)
                    for check in outcome.result.validation_checks
                ],
            }
            if outcome.result.error is not None:
                payload["error"] = dict(outcome.result.error)

        if outcome.error is not None:
            payload["runtime_error"] = outcome.error.to_dict()

        conversation = request.conversation + (
            {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "decision_type": IntelligenceDecisionType.TOOL_PROPOSAL.value,
                        "tool": call.tool,
                        "operation": call.operation,
                    },
                    sort_keys=True,
                ),
            },
            {
                "role": "tool",
                "name": call.tool,
                "content": json.dumps(payload, sort_keys=True),
            },
        )

        return IntelligenceRequest(
            request_id=request.request_id,
            task_id=request.task_id,
            user_intent=request.user_intent,
            conversation=conversation,
            metadata=request.metadata,
        )
