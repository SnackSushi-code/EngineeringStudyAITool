from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from anne_runtime.contracts import (
    PermissionClass,
    PermissionScope,
    RetryMode,
    TaskRequest,
    TaskState,
    ToolCall,
    ToolResult,
)
from anne_runtime.intelligence_contracts import (
    IntelligenceDecision,
    IntelligenceDecisionType,
    IntelligenceRequest,
    IntelligenceResult,
)
from anne_runtime.intelligence_orchestrator import IntelligenceInvocation
from anne_runtime.intelligence_runtime_bridge import (
    IntelligenceRuntimeBridge,
    IntelligenceRuntimeBridgeError,
)
from anne_runtime.model_contracts import FinishReason
from anne_runtime.orchestrator import TaskOutcome


def make_request() -> IntelligenceRequest:
    return IntelligenceRequest(
        request_id=uuid4(),
        task_id=uuid4(),
        user_intent="Use the test tool.",
        metadata={"source": "phase-1c-c-test"},
    )


def make_task_request(request: IntelligenceRequest) -> TaskRequest:
    return TaskRequest(
        schema_version="1.0",
        request_id=request.request_id,
        task_id=request.task_id,
        created_at="2026-09-20T00:00:00Z",
        source="phase-1c-c-test",
        user_intent=request.user_intent,
        priority="normal",
        workspace_id=uuid4(),
        requested_capabilities=("test.counter",),
        approval_required=False,
        approval_id=None,
        input_artifacts=(),
    )


def make_call(request: IntelligenceRequest) -> ToolCall:
    return ToolCall(
        schema_version="1.0",
        request_id=request.request_id,
        task_id=request.task_id,
        tool="test.counter",
        operation="execute",
        arguments={"value": "hello"},
        permissions=(
            PermissionScope(PermissionClass.READ, "test:value"),
        ),
        timeout_ms=1000,
        retry_mode=RetryMode.NONE,
        idempotency_key=str(uuid4()),
    )


def make_invocation(
    request: IntelligenceRequest,
    *,
    decision_type: IntelligenceDecisionType = IntelligenceDecisionType.TOOL_PROPOSAL,
    call: ToolCall | None = None,
) -> IntelligenceInvocation:
    if decision_type == IntelligenceDecisionType.TOOL_PROPOSAL:
        decision = IntelligenceDecision(
            decision_type=decision_type,
            tool_call=call or make_call(request),
        )
    else:
        decision = IntelligenceDecision(
            decision_type=decision_type,
            response_text="Done.",
        )

    result = IntelligenceResult(
        request=request,
        decision=decision,
        model_request_id=str(request.request_id),
        model_task_id=str(request.task_id),
    )

    return IntelligenceInvocation(
        result=result,
        provider_id="deterministic",
        provider_version="1.0.0",
        model="deterministic-v1",
        finish_reason=FinishReason.STOP,
        duration_seconds=0.001,
    )


@dataclass
class RecordingTaskOrchestrator:
    calls: list[tuple[TaskRequest, ToolCall, object | None]]

    def run(self, request, call, cancellation=None):
        self.calls.append((request, call, cancellation))
        return TaskOutcome(
            request_id=request.request_id,
            task_id=request.task_id,
            state=TaskState.SUCCEEDED,
            result=None,
            error=None,
            lifecycle=(),
        )


def test_tool_proposal_crosses_only_through_task_orchestrator():
    request = make_request()
    task_request = make_task_request(request)
    invocation = make_invocation(request)
    recorder = RecordingTaskOrchestrator(calls=[])

    outcome = IntelligenceRuntimeBridge(recorder).execute_proposal(
        invocation,
        task_request,
    )

    assert outcome.state == TaskState.SUCCEEDED
    assert len(recorder.calls) == 1
    recorded_request, recorded_call, cancellation = recorder.calls[0]
    assert recorded_request is task_request
    assert recorded_call is invocation.result.decision.tool_call
    assert cancellation is None


def test_final_response_cannot_enter_runtime_bridge():
    request = make_request()
    task_request = make_task_request(request)
    invocation = make_invocation(
        request,
        decision_type=IntelligenceDecisionType.FINAL_RESPONSE,
    )
    recorder = RecordingTaskOrchestrator(calls=[])

    with pytest.raises(
        IntelligenceRuntimeBridgeError,
        match="only TOOL_PROPOSAL",
    ):
        IntelligenceRuntimeBridge(recorder).execute_proposal(
            invocation,
            task_request,
        )

    assert recorder.calls == []


def test_request_id_mismatch_is_rejected_before_runtime():
    request = make_request()
    task_request = make_task_request(request)
    other = make_request()
    invocation = make_invocation(request)
    mismatched = TaskRequest(
        schema_version=task_request.schema_version,
        request_id=other.request_id,
        task_id=task_request.task_id,
        created_at=task_request.created_at,
        source=task_request.source,
        user_intent=task_request.user_intent,
        priority=task_request.priority,
        workspace_id=task_request.workspace_id,
        requested_capabilities=task_request.requested_capabilities,
        approval_required=task_request.approval_required,
        approval_id=task_request.approval_id,
        input_artifacts=task_request.input_artifacts,
    )
    recorder = RecordingTaskOrchestrator(calls=[])

    with pytest.raises(
        IntelligenceRuntimeBridgeError,
        match="request_id",
    ):
        IntelligenceRuntimeBridge(recorder).execute_proposal(
            invocation,
            mismatched,
        )

    assert recorder.calls == []


def test_task_id_mismatch_is_rejected_before_runtime():
    request = make_request()
    task_request = make_task_request(request)
    other = make_request()
    invocation = make_invocation(request)
    mismatched = TaskRequest(
        schema_version=task_request.schema_version,
        request_id=task_request.request_id,
        task_id=other.task_id,
        created_at=task_request.created_at,
        source=task_request.source,
        user_intent=task_request.user_intent,
        priority=task_request.priority,
        workspace_id=task_request.workspace_id,
        requested_capabilities=task_request.requested_capabilities,
        approval_required=task_request.approval_required,
        approval_id=task_request.approval_id,
        input_artifacts=task_request.input_artifacts,
    )
    recorder = RecordingTaskOrchestrator(calls=[])

    with pytest.raises(
        IntelligenceRuntimeBridgeError,
        match="task_id",
    ):
        IntelligenceRuntimeBridge(recorder).execute_proposal(
            invocation,
            mismatched,
        )

    assert recorder.calls == []


def test_tool_call_request_id_mismatch_is_rejected():
    request = make_request()
    task_request = make_task_request(request)
    invocation = make_invocation(request)
    valid_call = invocation.result.decision.tool_call
    assert valid_call is not None

    mismatched_call = ToolCall(
        schema_version=valid_call.schema_version,
        request_id=uuid4(),
        task_id=valid_call.task_id,
        tool=valid_call.tool,
        operation=valid_call.operation,
        arguments=dict(valid_call.arguments),
        permissions=valid_call.permissions,
        timeout_ms=valid_call.timeout_ms,
        retry_mode=valid_call.retry_mode,
        idempotency_key=valid_call.idempotency_key,
    )

    # IntelligenceResult intentionally rejects this invalid correlation during
    # normal construction. This test is specifically for the bridge's
    # defense-in-depth check, so construct the invalid result without invoking
    # the dataclass invariant a second time.
    forged_result = object.__new__(type(invocation.result))
    object.__setattr__(forged_result, "request", invocation.result.request)
    object.__setattr__(
        forged_result,
        "decision",
        IntelligenceDecision(
            decision_type=IntelligenceDecisionType.TOOL_PROPOSAL,
            tool_call=mismatched_call,
        ),
    )
    object.__setattr__(
        forged_result,
        "model_request_id",
        invocation.result.model_request_id,
    )
    object.__setattr__(
        forged_result,
        "model_task_id",
        invocation.result.model_task_id,
    )

    forged_invocation = IntelligenceInvocation(
        result=forged_result,
        provider_id=invocation.provider_id,
        provider_version=invocation.provider_version,
        model=invocation.model,
        finish_reason=invocation.finish_reason,
        duration_seconds=invocation.duration_seconds,
    )

    recorder = RecordingTaskOrchestrator(calls=[])

    with pytest.raises(
        IntelligenceRuntimeBridgeError,
        match="ToolCall request_id",
    ):
        IntelligenceRuntimeBridge(recorder).execute_proposal(
            forged_invocation,
            task_request,
        )

    assert recorder.calls == []


def test_cancellation_token_is_forwarded_unchanged():
    from anne_runtime.cancellation import CancellationToken

    request = make_request()
    task_request = make_task_request(request)
    invocation = make_invocation(request)
    recorder = RecordingTaskOrchestrator(calls=[])
    cancellation = CancellationToken()

    IntelligenceRuntimeBridge(recorder).execute_proposal(
        invocation,
        task_request,
        cancellation,
    )

    assert recorder.calls[0][2] is cancellation
