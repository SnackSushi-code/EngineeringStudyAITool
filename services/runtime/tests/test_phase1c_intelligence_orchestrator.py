from __future__ import annotations

import json
from dataclasses import replace
from uuid import uuid4

import pytest

from anne_runtime.contracts import RetryMode
from anne_runtime.deterministic_provider import DeterministicModelProvider
from anne_runtime.intelligence_contracts import (
    IntelligenceDecisionType,
    IntelligenceRequest,
)
from anne_runtime.intelligence_orchestrator import (
    IntelligenceOrchestrationError,
    IntelligenceOrchestrator,
)
from anne_runtime.model_contracts import FinishReason
from anne_runtime.model_router import ModelRouter
from anne_runtime.model_service import ModelService
from anne_runtime.provider_registry import ProviderRegistry


def make_request() -> IntelligenceRequest:
    return IntelligenceRequest(
        request_id=uuid4(),
        task_id=uuid4(),
        user_intent="Test Ann-E intelligence.",
        metadata={"source": "phase-1c-b-test"},
    )


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


def final_response_responder(_):
    return json.dumps(
        {
            "contract_version": "1.0",
            "decision_type": "FINAL_RESPONSE",
            "response_text": "Hello from Ann-E.",
        }
    )


def test_final_response_is_orchestrated():
    request = make_request()

    invocation = IntelligenceOrchestrator(
        make_service(final_response_responder)
    ).process(request)

    assert invocation.result.request.request_id == request.request_id
    assert (
        invocation.result.decision.decision_type
        == IntelligenceDecisionType.FINAL_RESPONSE
    )
    assert invocation.result.decision.response_text == "Hello from Ann-E."
    assert invocation.provider_id == "deterministic"
    assert invocation.model == "deterministic-v1"


def test_model_correlation_is_preserved():
    request = make_request()

    invocation = IntelligenceOrchestrator(
        make_service(final_response_responder)
    ).process(request)

    assert invocation.result.model_request_id == str(request.request_id)
    assert invocation.result.model_task_id == str(request.task_id)


def test_invalid_json_is_rejected():
    request = make_request()
    orchestrator = IntelligenceOrchestrator(
        make_service(lambda _: "not json")
    )

    with pytest.raises(
        IntelligenceOrchestrationError,
        match="not valid JSON",
    ):
        orchestrator.process(request)


def test_non_object_json_is_rejected():
    request = make_request()
    orchestrator = IntelligenceOrchestrator(
        make_service(lambda _: "[]")
    )

    with pytest.raises(
        IntelligenceOrchestrationError,
        match="JSON object",
    ):
        orchestrator.process(request)


def test_unknown_decision_type_is_rejected():
    request = make_request()
    orchestrator = IntelligenceOrchestrator(
        make_service(
            lambda _: json.dumps(
                {"decision_type": "EXECUTE_ANYTHING"}
            )
        )
    )

    with pytest.raises(
        IntelligenceOrchestrationError,
        match="unsupported decision_type",
    ):
        orchestrator.process(request)


def test_final_response_requires_text():
    request = make_request()
    orchestrator = IntelligenceOrchestrator(
        make_service(
            lambda _: json.dumps(
                {"decision_type": "FINAL_RESPONSE"}
            )
        )
    )

    with pytest.raises(
        IntelligenceOrchestrationError,
        match="response_text",
    ):
        orchestrator.process(request)


def test_final_response_cannot_contain_tool_call():
    request = make_request()
    orchestrator = IntelligenceOrchestrator(
        make_service(
            lambda _: json.dumps(
                {
                    "decision_type": "FINAL_RESPONSE",
                    "response_text": "No tool needed.",
                    "tool_call": {},
                }
            )
        )
    )

    with pytest.raises(
        IntelligenceOrchestrationError,
        match="tool_call",
    ):
        orchestrator.process(request)


def valid_tool_payload(request: IntelligenceRequest) -> dict:
    return {
        "contract_version": "1.0",
        "decision_type": "TOOL_PROPOSAL",
        "tool_call": {
            "schema_version": "1.0",
            "request_id": str(request.request_id),
            "task_id": str(request.task_id),
            "tool": "test.counter",
            "operation": "execute",
            "arguments": {"value": "hello"},
            "permissions": [
                {
                    "permission_class": "READ",
                    "scope": "test:value",
                }
            ],
            "timeout_ms": 1000,
            "retry_mode": RetryMode.NONE.value,
            "idempotency_key": str(uuid4()),
        },
    }


def test_tool_proposal_is_decoded_but_not_executed():
    request = make_request()

    invocation = IntelligenceOrchestrator(
        make_service(
            lambda _: json.dumps(valid_tool_payload(request))
        )
    ).process(request)

    decision = invocation.result.decision

    assert decision.decision_type == IntelligenceDecisionType.TOOL_PROPOSAL
    assert decision.tool_call is not None
    assert decision.tool_call.tool == "test.counter"


def test_tool_proposal_requires_tool_call():
    request = make_request()
    orchestrator = IntelligenceOrchestrator(
        make_service(
            lambda _: json.dumps(
                {"decision_type": "TOOL_PROPOSAL"}
            )
        )
    )

    with pytest.raises(
        IntelligenceOrchestrationError,
        match="tool_call",
    ):
        orchestrator.process(request)


def test_tool_proposal_cannot_contain_response_text():
    request = make_request()
    payload = valid_tool_payload(request)
    payload["response_text"] = "Do something."

    orchestrator = IntelligenceOrchestrator(
        make_service(lambda _: json.dumps(payload))
    )

    with pytest.raises(
        IntelligenceOrchestrationError,
        match="response_text",
    ):
        orchestrator.process(request)


def test_tool_proposal_correlation_is_enforced():
    request = make_request()
    payload = valid_tool_payload(request)
    payload["tool_call"]["task_id"] = str(uuid4())

    orchestrator = IntelligenceOrchestrator(
        make_service(lambda _: json.dumps(payload))
    )

    with pytest.raises(
        IntelligenceOrchestrationError,
        match="invalid tool_call",
    ):
        orchestrator.process(request)


def test_invalid_tool_arguments_container_is_rejected():
    request = make_request()
    payload = valid_tool_payload(request)
    payload["tool_call"]["arguments"] = ["not", "an", "object"]

    orchestrator = IntelligenceOrchestrator(
        make_service(lambda _: json.dumps(payload))
    )

    with pytest.raises(
        IntelligenceOrchestrationError,
        match="invalid tool_call",
    ):
        orchestrator.process(request)


def test_unsupported_finish_reason_is_rejected():
    request = make_request()

    class NonStopProvider(DeterministicModelProvider):
        def generate(self, model_request):
            response = super().generate(model_request)
            return replace(
                response,
                finish_reason=FinishReason.LENGTH,
            )

    registry = ProviderRegistry()
    registry.register(NonStopProvider())

    service = ModelService(
        ModelRouter(
            registry,
            default_provider_id="deterministic",
            default_model="deterministic-v1",
        )
    )

    with pytest.raises(
        IntelligenceOrchestrationError,
        match="finish reason",
    ):
        IntelligenceOrchestrator(service).process(request)


def test_model_failure_is_wrapped_without_execution():
    request = make_request()

    class FailingProvider(DeterministicModelProvider):
        def generate(self, model_request):
            raise RuntimeError("provider failure")

    registry = ProviderRegistry()
    registry.register(FailingProvider())

    service = ModelService(
        ModelRouter(
            registry,
            default_provider_id="deterministic",
            default_model="deterministic-v1",
        )
    )

    with pytest.raises(
        IntelligenceOrchestrationError,
        match="model invocation failed",
    ):
        IntelligenceOrchestrator(service).process(request)


def test_tool_proposal_uses_exact_runtime_correlation():
    request = make_request()
    payload = valid_tool_payload(request)

    invocation = IntelligenceOrchestrator(
        make_service(lambda _: json.dumps(payload))
    ).process(request)

    call = invocation.result.decision.tool_call
    assert call is not None
    assert call.request_id == request.request_id
    assert call.task_id == request.task_id
