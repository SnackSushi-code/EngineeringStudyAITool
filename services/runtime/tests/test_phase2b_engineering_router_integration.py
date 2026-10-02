from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from anne_runtime.engineering_capability_router import (
    EngineeringCapabilityRequest,
    EngineeringCapabilityRouter,
)
from anne_runtime.intelligence_contracts import (
    IntelligenceDecisionType,
    IntelligenceRequest,
)
from anne_runtime.intelligence_orchestrator import IntelligenceOrchestrator
from anne_runtime.intelligence_tool_authority import ToolAuthorityResolver
from anne_runtime.model_contracts import FinishReason
from anne_runtime.runtime_application import RuntimeApplication


class RecordingModelService:
    def __init__(self, response_payload: dict) -> None:
        self.response_payload = response_payload
        self.requests = []

    def invoke(self, request):
        self.requests.append(request)

        class Invocation:
            def __init__(self, model_request, payload):
                self.request = model_request
                self.response = type(
                    "Response",
                    (),
                    {
                        "request_id": model_request.request_id,
                        "task_id": model_request.task_id,
                        "provider_id": "test",
                        "provider_version": "phase2b-test",
                        "model": "phase2b-test",
                        "finish_reason": FinishReason.STOP,
                        "content": json.dumps(payload),
                        "raw_text": json.dumps(payload),
                        "parsed": payload,
                    },
                )()
                self.duration_seconds = 0.0

        return Invocation(request, self.response_payload)


def make_live_application() -> RuntimeApplication:
    return RuntimeApplication(Path.cwd())


def make_request() -> IntelligenceRequest:
    return IntelligenceRequest(
        request_id=uuid4(),
        task_id=uuid4(),
        user_intent="Calculate thermodynamic pressure.",
        metadata={
            "source": "phase-2b-router-integration-test",
            "anne.engineering.capability": "engineering.thermodynamics",
            "anne.engineering.domain": "mechanical",
            "anne.engineering.execution_type": "native",
            "anne.engineering.input_artifacts": "thermodynamics_specification",
            "anne.engineering.output_artifacts": "calculation_result",
        },
    )


def test_live_catalog_routes_candidates_into_model_without_granting_authority():
    app = make_live_application()

    registry = app._tool_registry
    catalog = app._capability_catalog
    router = EngineeringCapabilityRouter(catalog.snapshot())

    descriptor, handler = registry.get("anne.thermodynamics")

    assert descriptor.tool_id == "anne.thermodynamics"
    assert descriptor.version
    assert descriptor.capabilities == ("engineering.thermodynamics",)
    assert descriptor.engineering_domain == "mechanical"
    assert descriptor.execution_type.value == "native"
    assert handler.__name__ == "thermodynamics_handler"

    candidates = router.route(
        EngineeringCapabilityRequest(
            capability="engineering.thermodynamics",
            engineering_domain="mechanical",
            execution_type="native",
            input_artifact_types=("thermodynamics_specification",),
            output_artifact_types=("calculation_result",),
        )
    )

    assert candidates

    candidate = candidates[0]

    assert candidate.tool_id == descriptor.tool_id
    assert candidate.version == descriptor.version
    assert candidate.description == descriptor.description
    assert candidate.engineering_domain == descriptor.engineering_domain
    assert candidate.execution_type == descriptor.execution_type.value
    assert candidate.required_software == descriptor.required_software
    assert candidate.input_artifact_types == descriptor.input_artifact_types
    assert candidate.output_artifact_types == descriptor.output_artifact_types

    forbidden_fields = {
        "permissions",
        "required_permissions",
        "timeout_ms",
        "max_timeout_ms",
        "retry_mode",
        "idempotency_key",
        "handler",
        "execute",
    }

    assert forbidden_fields.isdisjoint(candidate.__dict__.keys())

    request = make_request()

    expected_proposal = {
        "decision_type": IntelligenceDecisionType.TOOL_PROPOSAL.value,
        "tool_call": {
            "request_id": str(request.request_id),
            "task_id": str(request.task_id),
            "tool": "anne.thermodynamics",
            "operation": "ideal_gas_pressure",
            "arguments": {
                "operation": "ideal_gas_pressure",
            },
        },
    }

    model_service = RecordingModelService(expected_proposal)

    intelligence = IntelligenceOrchestrator(
        model_service,
        capability_catalog=catalog,
        engineering_router=router,
    )

    invocation = intelligence.process(request)

    assert len(model_service.requests) == 1

    model_request = model_service.requests[0]
    metadata = model_request.metadata

    assert "anne.tool_catalog" in metadata
    assert "anne.engineering_candidates" in metadata

    routed_candidates = json.loads(
        metadata["anne.engineering_candidates"]
    )

    assert routed_candidates

    thermodynamics_candidates = [
        candidate
        for candidate in routed_candidates
        if candidate["tool_id"] == descriptor.tool_id
    ]

    assert thermodynamics_candidates

    routed = thermodynamics_candidates[0]

    assert routed["tool_id"] == descriptor.tool_id
    assert routed["version"] == descriptor.version
    assert routed["description"] == descriptor.description
    assert routed["engineering_domain"] == descriptor.engineering_domain
    assert routed["execution_type"] == descriptor.execution_type.value
    assert routed["required_software"] == list(
        descriptor.required_software
    )
    assert routed["input_artifact_types"] == list(
        descriptor.input_artifact_types
    )
    assert routed["output_artifact_types"] == list(
        descriptor.output_artifact_types
    )

    assert forbidden_fields.isdisjoint(routed.keys())

    result = invocation.result
    decision = result.decision

    assert decision.decision_type == (
        IntelligenceDecisionType.TOOL_PROPOSAL
    )

    proposal = decision.tool_call

    assert proposal is not None
    assert proposal.tool == descriptor.tool_id
    assert proposal.operation == "ideal_gas_pressure"
    assert proposal.arguments == {
        "operation": "ideal_gas_pressure",
    }
    assert proposal.request_id == request.request_id
    assert proposal.task_id == request.task_id

    assert invocation.provider_id == "test"
    assert invocation.provider_version == "phase2b-test"
    assert invocation.model == "phase2b-test"
    assert invocation.finish_reason == FinishReason.STOP
    assert invocation.duration_seconds == 0.0


def test_authority_still_derives_execution_controls_from_live_descriptor():
    app = make_live_application()

    registry = app._tool_registry
    catalog = app._capability_catalog
    router = EngineeringCapabilityRouter(catalog.snapshot())

    descriptor, handler = registry.get("anne.thermodynamics")

    assert descriptor.tool_id == "anne.thermodynamics"
    assert handler.__name__ == "thermodynamics_handler"

    request = make_request()

    proposal = type(
        "Proposal",
        (),
        {
            "request_id": request.request_id,
            "task_id": request.task_id,
            "tool": "anne.thermodynamics",
            "operation": "ideal_gas_pressure",
            "arguments": {
                "operation": "ideal_gas_pressure",
            },
        },
    )()

    resolved = ToolAuthorityResolver(registry).resolve(proposal)

    assert resolved.call.tool == descriptor.tool_id
    assert resolved.call.permissions == descriptor.required_permissions
    assert resolved.call.timeout_ms == descriptor.max_timeout_ms
    assert resolved.call.retry_mode == descriptor.retry_mode
    assert resolved.call.idempotency_key
    assert resolved.call.idempotency_key.strip()

    candidate = router.route(
        EngineeringCapabilityRequest(
            capability="engineering.thermodynamics",
            engineering_domain="mechanical",
            execution_type="native",
        )
    )[0]

    assert candidate.tool_id == descriptor.tool_id
    assert candidate.version == descriptor.version
    assert candidate.engineering_domain == descriptor.engineering_domain
    assert candidate.execution_type == descriptor.execution_type.value

    assert not hasattr(candidate, "permissions")
    assert not hasattr(candidate, "required_permissions")
    assert not hasattr(candidate, "timeout_ms")
    assert not hasattr(candidate, "max_timeout_ms")
    assert not hasattr(candidate, "retry_mode")
    assert not hasattr(candidate, "idempotency_key")
    assert not hasattr(candidate, "handler")
    assert not hasattr(candidate, "execute")


def test_live_router_does_not_expose_authority_metadata():
    app = make_live_application()

    catalog = app._capability_catalog
    router = EngineeringCapabilityRouter(catalog.snapshot())

    candidates = router.route(
        EngineeringCapabilityRequest(
            capability="engineering.thermodynamics",
            engineering_domain="mechanical",
            execution_type="native",
        )
    )

    assert candidates

    candidate = candidates[0]

    assert candidate.tool_id == "anne.thermodynamics"

    forbidden_fields = {
        "permissions",
        "required_permissions",
        "timeout_ms",
        "max_timeout_ms",
        "retry_mode",
        "idempotency_key",
        "handler",
        "execute",
    }

    assert forbidden_fields.isdisjoint(candidate.__dict__.keys())
