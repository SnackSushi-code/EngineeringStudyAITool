from __future__ import annotations

import pytest
from pathlib import Path

from anne_runtime.runtime_application import RuntimeApplication
from anne_runtime.contracts import PermissionClass, PermissionScope
from anne_runtime.tool_contracts import ToolCall, RetryMode

from anne_runtime.unit_conversion_tool import (
    UnitConversionError,
    convert_units,
)


@pytest.mark.parametrize(
    ("value", "from_unit", "to_unit", "expected"),
    [
        (1, "m", "cm", 100.0),
        (1, "km", "m", 1000.0),
        (12, "in", "ft", 1.0),
        (1, "mile", "km", 1.609344),
        (1, "kg", "g", 1000.0),
        (1, "lb", "kg", 0.45359237),
        (60, "s", "min", 1.0),
        (2, "h", "s", 7200.0),
        (1, "m2", "cm2", 10000.0),
        (1, "L", "m3", 0.001),
        (100, "km/h", "m/s", pytest.approx(27.7777777778)),
        (10, "m/s", "km/h", pytest.approx(36.0)),
        (1, "kN", "N", 1000.0),
        (1, "psi", "Pa", pytest.approx(6894.757293168)),
        (1, "kWh", "J", 3_600_000.0),
        (1, "kW", "W", 1000.0),
    ],
)
def test_convert_units(value, from_unit, to_unit, expected):
    assert convert_units(value, from_unit, to_unit) == expected


@pytest.mark.parametrize(
    ("value", "from_unit", "to_unit", "expected"),
    [
        (0, "C", "F", 32.0),
        (100, "C", "F", 212.0),
        (32, "F", "C", 0.0),
        (212, "F", "C", 100.0),
        (0, "C", "K", 273.15),
        (273.15, "K", "C", 0.0),
    ],
)
def test_temperature_conversion(value, from_unit, to_unit, expected):
    assert convert_units(value, from_unit, to_unit) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("value", "from_unit", "to_unit"),
    [
        (1, "m", "kg"),
        (1, "s", "m"),
        (1, "N", "J"),
        (1, "Pa", "W"),
        (1, "C", "m"),
        (1, "m", "C"),
    ],
)
def test_rejects_incompatible_units(value, from_unit, to_unit):
    with pytest.raises(UnitConversionError):
        convert_units(value, from_unit, to_unit)


@pytest.mark.parametrize(
    ("value", "from_unit", "to_unit"),
    [
        (1, "made_up_unit", "m"),
        (1, "m", "made_up_unit"),
    ],
)
def test_rejects_unknown_units(value, from_unit, to_unit):
    with pytest.raises(UnitConversionError):
        convert_units(value, from_unit, to_unit)


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        float("inf"),
        float("-inf"),
        float("nan"),
    ],
)
def test_rejects_invalid_values(value):
    with pytest.raises(UnitConversionError):
        convert_units(value, "m", "cm")


def test_rejects_empty_unit():
    with pytest.raises(UnitConversionError):
        convert_units(1, "", "m")


def test_unit_names_are_case_insensitive():
    assert convert_units(1, "KM", "m") == 1000.0
    assert convert_units(1, "kPa", "Pa") == 1000.0


def test_unit_names_allow_surrounding_whitespace():
    assert convert_units(1, " km ", " m ") == 1000.0
def test_runtime_registers_unit_conversion():
    app = RuntimeApplication(Path.cwd())

    descriptor = app._tool_registry.descriptor("anne.unit_convert")

    assert descriptor.tool_id == "anne.unit_convert"
    assert descriptor.version == "1.0.0"
    assert descriptor.capabilities == ("engineering.unit_conversion",)
    assert len(descriptor.required_permissions) == 1
    assert descriptor.required_permissions[0].scope == "anne/runtime/unit-conversion"
    assert descriptor.retry_mode is RetryMode.NONE
    assert descriptor.max_timeout_ms == 1000


def test_runtime_executes_unit_conversion():
    app = RuntimeApplication(Path.cwd())

    call = ToolCall(
        schema_version="1.0",
        request_id="test-unit-conversion-runtime",
        task_id="test-unit-conversion-runtime",
        tool="anne.unit_convert",
        operation="run",
        arguments={
            "value": 12,
            "from_unit": "in",
            "to_unit": "ft",
        },
        permissions=(
            PermissionScope(
                PermissionClass.READ,
                "anne/runtime/unit-conversion",
            ),
        ),
        timeout_ms=1000,
        retry_mode=RetryMode.NONE,
        idempotency_key="test-unit-conversion-runtime",
    )

    result = app._tool_executor.execute(call)

    assert result.status.value == "SUCCEEDED"
    assert result.tool == "anne.unit_convert"
    assert result.tool_version == "1.0.0"
    assert result.error is None
    assert result.result["value"] == 12
    assert result.result["from_unit"] == "in"
    assert result.result["to_unit"] == "ft"
    assert result.result["result"] == 1.0
