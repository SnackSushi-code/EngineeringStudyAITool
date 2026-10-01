from __future__ import annotations

from anne_runtime.engineering_capability_router import (
    EngineeringCapabilityRequest,
    EngineeringCapabilityRouter,
)


def catalog() -> tuple[dict[str, object], ...]:
    return (
        {
            "tool_id": "anne.control.native",
            "version": "1.0.0",
            "description": "Native control analysis.",
            "capabilities": ["engineering.control_analysis"],
            "engineering_domain": "controls",
            "execution_type": "native",
            "required_software": [],
            "input_artifact_types": ["model_specification"],
            "output_artifact_types": ["analysis_result"],
            "arguments": {"required": [], "properties": {}},
        },
        {
            "tool_id": "anne.control.matlab",
            "version": "1.0.0",
            "description": "MATLAB/Simulink control simulation.",
            "capabilities": [
                "engineering.control_analysis",
                "engineering.simulation",
            ],
            "engineering_domain": "controls",
            "execution_type": "external_software",
            "required_software": ["MATLAB", "Simulink"],
            "input_artifact_types": ["model_specification"],
            "output_artifact_types": ["simulation_result"],
            "arguments": {"required": [], "properties": {}},
        },
        {
            "tool_id": "anne.circuit.native",
            "version": "1.0.0",
            "description": "Native circuit analysis.",
            "capabilities": ["engineering.circuit_analysis"],
            "engineering_domain": "electrical",
            "execution_type": "native",
            "required_software": [],
            "input_artifact_types": ["circuit_specification"],
            "output_artifact_types": ["calculation_result"],
            "arguments": {"required": [], "properties": {}},
        },
    )


def test_router_returns_only_matching_capability_candidates():
    router = EngineeringCapabilityRouter(catalog())

    candidates = router.route(
        EngineeringCapabilityRequest(
            capability="engineering.control_analysis",
        )
    )

    assert {item.tool_id for item in candidates} == {
        "anne.control.native",
        "anne.control.matlab",
    }
    assert candidates[0].tool_id == "anne.control.matlab"


def test_router_prefers_domain_and_artifact_matches_deterministically():
    router = EngineeringCapabilityRouter(catalog())

    candidates = router.route(
        EngineeringCapabilityRequest(
            capability="engineering.control_analysis",
            engineering_domain="controls",
            input_artifact_types=("model_specification",),
            output_artifact_types=("simulation_result",),
        )
    )

    assert candidates[0].tool_id == "anne.control.matlab"
    assert candidates[0].score > candidates[1].score


def test_router_enforces_requested_software_requirements():
    router = EngineeringCapabilityRouter(catalog())

    candidates = router.route(
        EngineeringCapabilityRequest(
            capability="engineering.control_analysis",
            required_software=("MATLAB", "Simulink"),
        )
    )

    assert [item.tool_id for item in candidates] == ["anne.control.matlab"]


def test_router_rejects_candidates_missing_requested_software():
    router = EngineeringCapabilityRouter(catalog())

    candidates = router.route(
        EngineeringCapabilityRequest(
            capability="engineering.control_analysis",
            required_software=("Python",),
        )
    )

    assert candidates == ()

def test_router_can_require_available_software():
    router = EngineeringCapabilityRouter(catalog())

    candidates = router.route(
        EngineeringCapabilityRequest(
            capability="engineering.control_analysis",
            available_software=("MATLAB",),
        )
    )

    assert [item.tool_id for item in candidates] == ["anne.control.native"]


def test_router_can_prefer_a_requested_execution_type():
    router = EngineeringCapabilityRouter(catalog())

    candidates = router.route(
        EngineeringCapabilityRequest(
            capability="engineering.control_analysis",
            execution_type="external_software",
        )
    )

    assert candidates[0].tool_id == "anne.control.matlab"


def test_router_is_deterministic_for_equal_matches():
    router = EngineeringCapabilityRouter(catalog())

    request = EngineeringCapabilityRequest(
        capability="engineering.control_analysis",
        engineering_domain="controls",
    )

    first = router.route(request)
    second = router.route(request)

    assert first == second


def test_router_output_contains_no_authority_fields():
    router = EngineeringCapabilityRouter(catalog())

    candidate = router.route(
        EngineeringCapabilityRequest(
            capability="engineering.control_analysis"
        )
    )[0]

    assert not hasattr(candidate, "permissions")
    assert not hasattr(candidate, "timeout_ms")
    assert not hasattr(candidate, "retry_mode")
    assert not hasattr(candidate, "idempotency_key")
