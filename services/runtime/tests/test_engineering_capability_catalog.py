from __future__ import annotations

import json

import pytest

from anne_runtime.contracts import PermissionClass, PermissionScope, RetryMode
from anne_runtime.intelligence_tool_authority import ToolCapabilityCatalog
from anne_runtime.tool_contracts import (
    ToolArgument,
    ToolArgumentSchema,
    ToolContractError,
    ToolDescriptor,
    ToolExecutionType,
    ToolValueType,
)
from anne_runtime.tool_registry import ToolRegistry


def engineering_registry() -> ToolRegistry:
    registry = ToolRegistry()

    registry.register(
        ToolDescriptor(
            tool_id="anne.test_circuit",
            version="1.0.0",
            description="Test circuit analysis capability.",
            capabilities=("engineering.circuit_analysis",),
            engineering_domain="electrical",
            execution_type=ToolExecutionType.NATIVE,
            required_software=(),
            input_artifact_types=("circuit_specification",),
            output_artifact_types=("calculation_result",),
            arguments=ToolArgumentSchema(
                arguments=(
                    ToolArgument(
                        name="voltage",
                        value_type=ToolValueType.NUMBER,
                        required=True,
                        description="Circuit voltage.",
                    ),
                )
            ),
            required_permissions=(
                PermissionScope(
                    PermissionClass.READ,
                    "anne/runtime/test-circuit",
                ),
            ),
            retry_mode=RetryMode.NONE,
            max_timeout_ms=1000,
        ),
        lambda context, arguments: {"current": 1.0},
    )

    return registry


def test_engineering_metadata_is_exposed_to_catalog():
    catalog = ToolCapabilityCatalog(engineering_registry())

    entry = catalog.snapshot()[0]

    assert entry["tool_id"] == "anne.test_circuit"
    assert entry["engineering_domain"] == "electrical"
    assert entry["execution_type"] == "native"
    assert entry["required_software"] == []
    assert entry["input_artifact_types"] == ["circuit_specification"]
    assert entry["output_artifact_types"] == ["calculation_result"]


def test_catalog_remains_free_of_authority_fields():
    payload = json.dumps(
        ToolCapabilityCatalog(engineering_registry()).snapshot()
    )

    for forbidden in (
        "permissions",
        "required_permissions",
        "timeout_ms",
        "max_timeout_ms",
        "retry_mode",
        "idempotency_key",
    ):
        assert forbidden not in payload


def test_external_software_metadata_is_supported():
    registry = ToolRegistry()

    registry.register(
        ToolDescriptor(
            tool_id="anne.test_matlab",
            version="1.0.0",
            description="Test MATLAB-backed capability.",
            capabilities=("engineering.control",),
            engineering_domain="controls",
            execution_type=ToolExecutionType.EXTERNAL_SOFTWARE,
            required_software=("MATLAB", "Simulink"),
            input_artifact_types=("model_specification",),
            output_artifact_types=("simulation_result",),
            arguments=ToolArgumentSchema(),
            required_permissions=(
                PermissionScope(
                    PermissionClass.READ,
                    "anne/runtime/test-matlab",
                ),
            ),
        ),
        lambda context, arguments: {"ok": True},
    )

    entry = ToolCapabilityCatalog(registry).snapshot()[0]

    assert entry["engineering_domain"] == "controls"
    assert entry["execution_type"] == "external_software"
    assert entry["required_software"] == ["MATLAB", "Simulink"]
    assert entry["input_artifact_types"] == ["model_specification"]
    assert entry["output_artifact_types"] == ["simulation_result"]


def test_blank_engineering_domain_is_rejected():
    with pytest.raises(
        ToolContractError,
        match="Engineering domain cannot be blank",
    ):
        ToolDescriptor(
            tool_id="anne.invalid",
            version="1.0.0",
            description="Invalid descriptor.",
            capabilities=("engineering.test",),
            engineering_domain="   ",
            arguments=ToolArgumentSchema(),
            required_permissions=(),
        )
