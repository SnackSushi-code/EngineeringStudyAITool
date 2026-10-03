from __future__ import annotations

from uuid import uuid4

import pytest

from anne_runtime.contracts import TaskState, ToolResult
from anne_runtime.engineering_result import (
    EngineeringHandoff,
    EngineeringQuantity,
)


def make_result(
    *,
    result: dict[str, object] | None = None,
    artifacts: tuple[str, ...] = (),
    validation_state: str = "PASSED",
    validation_checks: tuple[dict[str, object], ...] = (),
    error: dict[str, object] | None = None,
) -> ToolResult:
    return ToolResult(
        schema_version="1.0",
        request_id=uuid4(),
        task_id=uuid4(),
        status=TaskState.SUCCEEDED,
        result=result or {"temperature": 300.0},
        artifacts=artifacts,
        validation_state=validation_state,
        validation_checks=validation_checks,
        tool="anne.thermodynamics",
        tool_version="1.0.0",
        adapter_version="tool-executor-1.0",
        error=error,
        logs=(),
    )


def test_engineering_handoff_preserves_runtime_correlation_and_provenance() -> None:
    result = make_result(
        artifacts=("artifact://thermal/result",),
        validation_checks=(
            {"check": "finite", "passed": True},
        ),
    )

    handoff = EngineeringHandoff.from_tool_result(
        result,
        operation="ideal_gas_temperature",
        quantities={
            "temperature": EngineeringQuantity(
                value=300.0,
                unit="K",
                dimension="temperature",
                unit_source="contract",
            )
        },
    )

    assert handoff.request_id == result.request_id
    assert handoff.task_id == result.task_id
    assert handoff.source_tool == "anne.thermodynamics"
    assert handoff.operation == "ideal_gas_temperature"
    assert handoff.artifacts == result.artifacts
    assert handoff.validation.state == "PASSED"
    assert handoff.provenance.tool == result.tool
    assert handoff.provenance.tool_version == result.tool_version
    assert handoff.provenance.adapter_version == result.adapter_version


def test_engineering_handoff_preserves_raw_values_without_guessing_units() -> None:
    result = make_result(
        result={
            "pressure": 101325.0,
            "volume": 0.0246,
        }
    )

    handoff = EngineeringHandoff.from_tool_result(
        result,
        operation="ideal_gas_volume",
    )

    assert handoff.values == {
        "pressure": 101325.0,
        "volume": 0.0246,
    }
    assert handoff.quantities == {}


def test_engineering_quantity_requires_explicit_unit_source() -> None:
    quantity = EngineeringQuantity(
        value=101325.0,
        unit="Pa",
        dimension="pressure",
        unit_source="explicit",
    )

    assert quantity.to_dict() == {
        "value": 101325.0,
        "unit": "Pa",
        "dimension": "pressure",
        "unit_source": "explicit",
    }


def test_engineering_quantity_rejects_missing_unit_with_non_unknown_source() -> None:
    with pytest.raises(ValueError, match="unit_source"):
        EngineeringQuantity(
            value=101325.0,
            dimension="pressure",
            unit_source="contract",
        )


def test_engineering_handoff_rejects_unknown_quantity_name() -> None:
    result = make_result(result={"pressure": 101325.0})

    with pytest.raises(
        ValueError,
        match="Engineering quantities reference values",
    ):
        EngineeringHandoff.from_tool_result(
            result,
            operation="ideal_gas_pressure",
            quantities={
                "temperature": EngineeringQuantity(
                    value=300.0,
                    unit="K",
                    dimension="temperature",
                    unit_source="explicit",
                )
            },
        )


def test_engineering_handoff_rejects_empty_operation() -> None:
    result = make_result()

    with pytest.raises(ValueError, match="operation"):
        EngineeringHandoff.from_tool_result(
            result,
            operation="",
        )


def test_engineering_handoff_preserves_error_payload() -> None:
    result = make_result(
        error={
            "code": "THERMODYNAMICS_ERROR",
            "message": "invalid input",
        }
    )

    handoff = EngineeringHandoff.from_tool_result(
        result,
        operation="ideal_gas_pressure",
    )

    assert handoff.error == {
        "code": "THERMODYNAMICS_ERROR",
        "message": "invalid input",
    }


def test_engineering_handoff_serialization_is_model_safe() -> None:
    result = make_result()

    handoff = EngineeringHandoff.from_tool_result(
        result,
        operation="ideal_gas_temperature",
        quantities={
            "temperature": EngineeringQuantity(
                value=300.0,
                unit="K",
                dimension="temperature",
                unit_source="contract",
            )
        },
    )

    serialized = handoff.to_dict()

    assert serialized["request_id"] == str(result.request_id)
    assert serialized["task_id"] == str(result.task_id)
    assert serialized["status"] == "SUCCEEDED"
    assert serialized["source_tool"] == "anne.thermodynamics"
    assert serialized["operation"] == "ideal_gas_temperature"
    assert serialized["values"]["temperature"] == 300.0
    assert serialized["quantities"]["temperature"]["unit"] == "K"
    assert serialized["provenance"]["tool"] == "anne.thermodynamics"

    # Authority/security metadata must not appear in the engineering handoff.
    assert "permissions" not in serialized
    assert "required_permissions" not in serialized
    assert "timeout_ms" not in serialized
    assert "max_timeout_ms" not in serialized
    assert "retry_mode" not in serialized
    assert "handler" not in serialized
