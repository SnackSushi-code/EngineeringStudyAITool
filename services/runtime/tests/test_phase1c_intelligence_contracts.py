from __future__ import annotations

from uuid import uuid4

import pytest

from anne_runtime.contracts import PermissionClass, PermissionScope, RetryMode, ToolCall
from anne_runtime.intelligence_contracts import (
    INTELLIGENCE_CONTRACT_VERSION,
    IntelligenceContractError,
    IntelligenceDecision,
    IntelligenceDecisionType,
    IntelligenceRequest,
    IntelligenceResult,
)
from anne_runtime.model_contracts import ModelRole


def make_request() -> IntelligenceRequest:
    return IntelligenceRequest(
        request_id=uuid4(),
        task_id=uuid4(),
        user_intent="Answer my engineering question.",
    )


def make_tool_call(request: IntelligenceRequest) -> ToolCall:
    return ToolCall(
        schema_version="1.0",
        request_id=request.request_id,
        task_id=request.task_id,
        tool="test.counter",
        operation="execute",
        arguments={"value": "hello"},
        permissions=(PermissionScope(PermissionClass.READ, "test:value"),),
        timeout_ms=1000,
        retry_mode=RetryMode.NONE,
        idempotency_key=str(uuid4()),
    )


def test_request_requires_uuid_ids() -> None:
    with pytest.raises(IntelligenceContractError):
        IntelligenceRequest(request_id="bad", task_id=uuid4(), user_intent="test")  # type: ignore[arg-type]


def test_request_requires_nonempty_intent() -> None:
    with pytest.raises(IntelligenceContractError):
        IntelligenceRequest(request_id=uuid4(), task_id=uuid4(), user_intent="")


def test_model_bridge_preserves_correlation() -> None:
    request = make_request()
    model_request = request.to_model_request()
    assert model_request.request_id == str(request.request_id)
    assert model_request.task_id == str(request.task_id)
    assert len(model_request.messages) == 1
    assert model_request.messages[0].role == ModelRole.USER
    assert model_request.messages[0].content == request.user_intent


def test_final_response_requires_text() -> None:
    with pytest.raises(IntelligenceContractError):
        IntelligenceDecision(decision_type=IntelligenceDecisionType.FINAL_RESPONSE)


def test_final_response_cannot_have_tool() -> None:
    request = make_request()
    with pytest.raises(IntelligenceContractError):
        IntelligenceDecision(
            decision_type=IntelligenceDecisionType.FINAL_RESPONSE,
            response_text="Done.",
            tool_call=make_tool_call(request),
        )


def test_tool_proposal_requires_tool() -> None:
    with pytest.raises(IntelligenceContractError):
        IntelligenceDecision(decision_type=IntelligenceDecisionType.TOOL_PROPOSAL)


def test_tool_proposal_cannot_have_response() -> None:
    request = make_request()
    with pytest.raises(IntelligenceContractError):
        IntelligenceDecision(
            decision_type=IntelligenceDecisionType.TOOL_PROPOSAL,
            response_text="Executing.",
            tool_call=make_tool_call(request),
        )


def test_result_requires_matching_model_correlation() -> None:
    request = make_request()
    result = IntelligenceResult(
        request=request,
        decision=IntelligenceDecision(
            decision_type=IntelligenceDecisionType.FINAL_RESPONSE,
            response_text="Completed.",
        ),
        model_request_id=str(request.request_id),
        model_task_id=str(request.task_id),
    )
    assert result.model_request_id == str(request.request_id)


def test_result_rejects_wrong_model_request_id() -> None:
    request = make_request()
    with pytest.raises(IntelligenceContractError):
        IntelligenceResult(
            request=request,
            decision=IntelligenceDecision(
                decision_type=IntelligenceDecisionType.FINAL_RESPONSE,
                response_text="Completed.",
            ),
            model_request_id=str(uuid4()),
            model_task_id=str(request.task_id),
        )


def test_result_rejects_mismatched_tool_call() -> None:
    request = make_request()
    other = make_request()
    with pytest.raises(IntelligenceContractError):
        IntelligenceResult(
            request=request,
            decision=IntelligenceDecision(
                decision_type=IntelligenceDecisionType.TOOL_PROPOSAL,
                tool_call=make_tool_call(other),
            ),
            model_request_id=str(request.request_id),
            model_task_id=str(request.task_id),
        )


def test_matching_tool_proposal_is_valid() -> None:
    request = make_request()
    result = IntelligenceResult(
        request=request,
        decision=IntelligenceDecision(
            decision_type=IntelligenceDecisionType.TOOL_PROPOSAL,
            tool_call=make_tool_call(request),
        ),
        model_request_id=str(request.request_id),
        model_task_id=str(request.task_id),
    )
    assert result.to_dict()["decision"]["decision_type"] == "TOOL_PROPOSAL"


def test_serialization() -> None:
    request = make_request()
    result = IntelligenceResult(
        request=request,
        decision=IntelligenceDecision(
            decision_type=IntelligenceDecisionType.FINAL_RESPONSE,
            response_text="Done.",
        ),
        model_request_id=str(request.request_id),
        model_task_id=str(request.task_id),
    )
    assert result.to_dict()["contract_version"] == INTELLIGENCE_CONTRACT_VERSION
