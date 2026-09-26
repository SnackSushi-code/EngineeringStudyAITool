from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import uuid4

import pytest

from anne_runtime.cancellation import CancellationToken
from anne_runtime.contracts import (
    PermissionClass,
    PermissionScope,
    RetryMode,
    TaskRequest,
    TaskState,
    ToolCall,
    ToolResult,
)
from anne_runtime.deterministic_provider import DeterministicModelProvider
from anne_runtime.intelligence_contracts import (
    IntelligenceDecisionType,
    IntelligenceRequest,
)
from anne_runtime.intelligence_orchestrator import IntelligenceOrchestrator
from anne_runtime.intelligence_planning_loop import (
    IntelligencePlanningError,
    IntelligencePlanningLoop,
)
from anne_runtime.intelligence_runtime_bridge import IntelligenceRuntimeBridge
from anne_runtime.intelligence_tool_authority import ToolAuthorityResolver
from anne_runtime.model_router import ModelRouter
from anne_runtime.model_service import ModelService
from anne_runtime.provider_registry import ProviderRegistry
from anne_runtime.orchestrator import TaskOutcome
from anne_runtime.tool_contracts import (
    ToolArgument,
    ToolArgumentSchema,
    ToolDescriptor,
    ToolValueType,
)
from anne_runtime.tool_registry import ToolRegistry


def make_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolDescriptor(
            tool_id="test.counter",
            version="1.0",
            description="Test counter tool",
            capabilities=frozenset({"READ"}),
            arguments=ToolArgumentSchema(
                arguments=(ToolArgument(
                        name="value",
                        value_type=ToolValueType.STRING,
                        required=True,
                        description="Test value",
                    ),)
            ),
            required_permissions=frozenset(
                {PermissionScope(PermissionClass.READ, "test:value")}
            ),
            retry_mode=RetryMode.NONE,
            max_timeout_ms=1000,
        ),
        lambda context, arguments: {"value": arguments["value"]},
    )
    return registry


def make_resolver() -> ToolAuthorityResolver:
    return ToolAuthorityResolver(make_registry())


def make_request() -> IntelligenceRequest:
    return IntelligenceRequest(
        request_id=uuid4(),
        task_id=uuid4(),
        user_intent="Use the test tool and report the result.",
        metadata={"source": "phase-1d-test"},
    )


def make_task_request(request: IntelligenceRequest) -> TaskRequest:
    return TaskRequest(
        schema_version="1.0",
        request_id=request.request_id,
        task_id=request.task_id,
        created_at="2026-09-20T00:00:00Z",
        source="phase-1d-test",
        user_intent=request.user_intent,
        priority="normal",
        workspace_id=uuid4(),
        requested_capabilities=("test.counter",),
        approval_required=False,
        approval_id=None,
        input_artifacts=(),
    )


def tool_payload(request: IntelligenceRequest) -> dict:
    return {
        "contract_version": "1.0",
        "decision_type": "TOOL_PROPOSAL",
        "tool_call": {
            "request_id": str(request.request_id),
            "task_id": str(request.task_id),
            "tool": "test.counter",
            "operation": "execute",
            "arguments": {"value": "hello"},
        },
    }


def make_service(responder) -> ModelService:
    registry = ProviderRegistry()
    registry.register(
        DeterministicModelProvider(responder=responder)
    )
    return ModelService(
        ModelRouter(
            registry,
            default_provider_id="deterministic",
            default_model="deterministic-v1",
        )
    )


@dataclass
class RecordingTaskOrchestrator:
    outcomes: list[TaskOutcome]
    calls: list[tuple[TaskRequest, ToolCall, CancellationToken | None]]

    def run(self, request, call, cancellation=None):
        self.calls.append((request, call, cancellation))
        return self.outcomes.pop(0)


def success_outcome(request: IntelligenceRequest) -> TaskOutcome:
    result = ToolResult(
        schema_version="1.0",
        request_id=request.request_id,
        task_id=request.task_id,
        status=TaskState.SUCCEEDED,
        result={"value": "42"},
        artifacts=("artifact://result",),
        validation_state="VALID",
        validation_checks=({"name": "basic", "passed": True},),
        tool="test.counter",
        tool_version="1.0",
        adapter_version="1.0",
        error=None,
        logs=("internal log that must not be forwarded as logs",),
    )
    return TaskOutcome(
        request_id=request.request_id,
        task_id=request.task_id,
        state=TaskState.SUCCEEDED,
        result=result,
        error=None,
        lifecycle=(),
    )


def failed_outcome(request: IntelligenceRequest) -> TaskOutcome:
    return TaskOutcome(
        request_id=request.request_id,
        task_id=request.task_id,
        state=TaskState.FAILED,
        result=None,
        error=None,
        lifecycle=(),
    )


def make_loop(responder, outcomes):
    intelligence = IntelligenceOrchestrator(make_service(responder))
    recorder = RecordingTaskOrchestrator(
        outcomes=list(outcomes),
        calls=[],
    )
    bridge = IntelligenceRuntimeBridge(recorder, make_resolver())
    return IntelligencePlanningLoop(
        intelligence,
        bridge,
        max_iterations=4,
    ), recorder


def test_final_response_completes_without_runtime_execution():
    request = make_request()
    task_request = make_task_request(request)

    def responder(model_request):
        assert len(model_request.messages) == 1
        return json.dumps(
            {
                "contract_version": "1.0",
                "decision_type": "FINAL_RESPONSE",
                "response_text": "Finished.",
            }
        )

    loop, recorder = make_loop(responder, [])

    outcome = loop.run(request, task_request)

    assert outcome.completed is True
    assert outcome.final_response == "Finished."
    assert outcome.stop_reason == "FINAL_RESPONSE"
    assert len(outcome.iterations) == 1
    assert recorder.calls == []


def test_successful_tool_is_followed_by_next_model_iteration():
    request = make_request()
    task_request = make_task_request(request)
    seen = []

    def responder(model_request):
        seen.append(model_request)
        if len(seen) == 1:
            return json.dumps(tool_payload(request))

        assert len(model_request.messages) == 3
        assert model_request.messages[0].content == request.user_intent
        assert model_request.messages[1].role.value == "assistant"
        assert model_request.messages[2].role.value == "tool"
        assert "internal log" not in model_request.messages[2].content
        assert '"value": "42"' in model_request.messages[2].content

        return json.dumps(
            {
                "contract_version": "1.0",
                "decision_type": "FINAL_RESPONSE",
                "response_text": "The tool returned 42.",
            }
        )

    loop, recorder = make_loop(
        responder,
        [success_outcome(request)],
    )

    outcome = loop.run(request, task_request)

    assert outcome.completed is True
    assert outcome.final_response == "The tool returned 42."
    assert outcome.stop_reason == "FINAL_RESPONSE"
    assert len(outcome.iterations) == 2
    assert len(recorder.calls) == 1


def test_non_successful_tool_stops_without_automatic_retry_loop():
    request = make_request()
    task_request = make_task_request(request)
    model_calls = 0

    def responder(model_request):
        nonlocal model_calls
        model_calls += 1
        return json.dumps(tool_payload(request))

    loop, recorder = make_loop(
        responder,
        [failed_outcome(request)],
    )

    outcome = loop.run(request, task_request)

    assert outcome.completed is False
    assert outcome.stop_reason == "TOOL_FAILED"
    assert len(outcome.iterations) == 1
    assert model_calls == 1
    assert len(recorder.calls) == 1


def test_max_iterations_bounds_repeated_successful_tools():
    request = make_request()
    task_request = make_task_request(request)
    model_calls = 0

    def responder(model_request):
        nonlocal model_calls
        model_calls += 1
        return json.dumps(tool_payload(request))

    loop, recorder = make_loop(
        responder,
        [
            success_outcome(request),
            success_outcome(request),
            success_outcome(request),
            success_outcome(request),
        ],
    )

    outcome = loop.run(request, task_request)

    assert outcome.completed is False
    assert outcome.stop_reason == "MAX_ITERATIONS"
    assert len(outcome.iterations) == 4
    assert model_calls == 4
    assert len(recorder.calls) == 4


def test_cancellation_stops_before_next_model_iteration():
    request = make_request()
    task_request = make_task_request(request)
    cancellation = CancellationToken()

    def responder(model_request):
        return json.dumps(tool_payload(request))

    class CancellingRecorder(RecordingTaskOrchestrator):
        def run(self, request, call, cancellation=None):
            result = super().run(request, call, cancellation)
            cancellation.request("test cancellation")
            return result

    cancelling_recorder = CancellingRecorder(
        outcomes=[success_outcome(request)],
        calls=[],
    )
    loop = IntelligencePlanningLoop(
        IntelligenceOrchestrator(make_service(responder)),
        IntelligenceRuntimeBridge(cancelling_recorder, make_resolver()),
        max_iterations=4,
    )

    outcome = loop.run(request, task_request, cancellation)

    assert outcome.completed is False
    assert outcome.stop_reason == "CANCELLED"
    assert len(outcome.iterations) == 1
    assert len(cancelling_recorder.calls) == 1


def test_request_and_task_correlation_is_required():
    request = make_request()
    other = make_request()
    task_request = make_task_request(other)

    loop, recorder = make_loop(
        lambda _: json.dumps(
            {
                "contract_version": "1.0",
                "decision_type": "FINAL_RESPONSE",
                "response_text": "unused",
            }
        ),
        [],
    )

    with pytest.raises(
        IntelligencePlanningError,
        match="request_id",
    ):
        loop.run(request, task_request)

    assert recorder.calls == []
