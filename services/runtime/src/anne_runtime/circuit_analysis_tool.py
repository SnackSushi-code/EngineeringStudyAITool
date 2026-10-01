import math
from typing import Any

from .tool_contracts import ToolExecutionError


MAX_RESISTANCE_COUNT = 10_000
MAX_ABSOLUTE_VALUE = 1e100


class CircuitAnalysisError(ToolExecutionError):
    """Raised when circuit-analysis inputs or calculations are invalid."""


def _validate_scalar(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise CircuitAnalysisError(f"{name} must be a finite number")

    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise CircuitAnalysisError(
            f"{name} must be a finite number"
        ) from exc

    if not math.isfinite(numeric):
        raise CircuitAnalysisError(f"{name} must be a finite number")

    if abs(numeric) > MAX_ABSOLUTE_VALUE:
        raise CircuitAnalysisError(
            f"{name} exceeds maximum supported magnitude "
            f"of {MAX_ABSOLUTE_VALUE}"
        )

    return numeric


def _validate_positive(value: Any, name: str) -> float:
    numeric = _validate_scalar(value, name)

    if numeric <= 0:
        raise CircuitAnalysisError(f"{name} must be positive")

    return numeric


def _validate_nonnegative(value: Any, name: str) -> float:
    numeric = _validate_scalar(value, name)

    if numeric < 0:
        raise CircuitAnalysisError(f"{name} must be nonnegative")

    return numeric


def _validate_resistance_list(resistances: Any) -> list[float]:
    if not isinstance(resistances, (list, tuple)):
        raise CircuitAnalysisError("resistances must be a list")

    if not resistances:
        raise CircuitAnalysisError("resistances must not be empty")

    if len(resistances) > MAX_RESISTANCE_COUNT:
        raise CircuitAnalysisError(
            f"resistances exceeds maximum length of "
            f"{MAX_RESISTANCE_COUNT}"
        )

    return [
        _validate_positive(resistance, "resistance")
        for resistance in resistances
    ]


def _require_arguments(
    arguments: dict[str, Any],
    names: tuple[str, ...],
) -> None:
    missing = [name for name in names if arguments.get(name) is None]

    if missing:
        raise CircuitAnalysisError(
            "Missing required arguments: " + ", ".join(missing)
        )


def _ohms_law(
    *,
    voltage: Any = None,
    current: Any = None,
    resistance: Any = None,
) -> dict[str, float]:
    supplied = {
        "voltage": voltage,
        "current": current,
        "resistance": resistance,
    }

    known = [
        name
        for name, value in supplied.items()
        if value is not None
    ]

    if len(known) != 2:
        raise CircuitAnalysisError(
            "ohms_law requires exactly two known values"
        )

    numeric = {
        name: _validate_scalar(value, name)
        for name, value in supplied.items()
        if value is not None
    }

    if "resistance" in numeric and numeric["resistance"] <= 0:
        raise CircuitAnalysisError("resistance must be positive")

    if "voltage" not in numeric:
        voltage_value = numeric["current"] * numeric["resistance"]
    else:
        voltage_value = numeric["voltage"]

    if "current" not in numeric:
        current_value = voltage_value / numeric["resistance"]
    else:
        current_value = numeric["current"]

    if "resistance" not in numeric:
        if current_value == 0:
            raise CircuitAnalysisError(
                "current must not be zero when calculating resistance"
            )
        resistance_value = voltage_value / current_value
        if resistance_value <= 0:
            raise CircuitAnalysisError(
                "calculated resistance must be positive"
            )
    else:
        resistance_value = numeric["resistance"]

    return {
        "operation": "ohms_law",
        "voltage": voltage_value,
        "current": current_value,
        "resistance": resistance_value,
    }


def _power(
    *,
    voltage: Any = None,
    current: Any = None,
    resistance: Any = None,
) -> dict[str, float]:
    supplied = {
        "voltage": voltage,
        "current": current,
        "resistance": resistance,
    }

    known = [
        name
        for name, value in supplied.items()
        if value is not None
    ]

    if len(known) != 2:
        raise CircuitAnalysisError(
            "power requires exactly two known values"
        )

    numeric = {
        name: _validate_scalar(value, name)
        for name, value in supplied.items()
        if value is not None
    }

    if "resistance" in numeric and numeric["resistance"] <= 0:
        raise CircuitAnalysisError("resistance must be positive")

    if "voltage" in numeric and "current" in numeric:
        voltage_value = numeric["voltage"]
        current_value = numeric["current"]

        if current_value == 0:
            raise CircuitAnalysisError(
                "current must not be zero when calculating resistance"
            )

        resistance_value = voltage_value / current_value

        if resistance_value <= 0:
            raise CircuitAnalysisError(
                "calculated resistance must be positive"
            )

        power_value = voltage_value * current_value

    elif "voltage" in numeric and "resistance" in numeric:
        voltage_value = numeric["voltage"]
        resistance_value = numeric["resistance"]
        current_value = voltage_value / resistance_value
        power_value = voltage_value * current_value

    else:
        current_value = numeric["current"]
        resistance_value = numeric["resistance"]
        voltage_value = current_value * resistance_value
        power_value = current_value * current_value * resistance_value

    return {
        "operation": "power",
        "power": power_value,
        "voltage": voltage_value,
        "current": current_value,
        "resistance": resistance_value,
    }


def circuit_analysis(
    operation: str,
    *,
    voltage: Any = None,
    current: Any = None,
    resistance: Any = None,
    resistances: Any = None,
    input_voltage: Any = None,
    r1: Any = None,
    r2: Any = None,
    total_current: Any = None,
    power: Any = None,
    time_seconds: Any = None,
    resistance_ohms: Any = None,
    capacitance_farads: Any = None,
    inductance_henries: Any = None,
    cancellation_check: Any = None,
) -> dict[str, Any]:
    """Perform safe deterministic circuit-analysis calculations."""

    operation_name = str(operation).strip().lower()

    supported_operations = {
        "ohms_law",
        "series_resistance",
        "parallel_resistance",
        "voltage_divider",
        "current_divider",
        "power",
        "energy",
        "rc_time_constant",
        "rl_time_constant",
    }

    if operation_name not in supported_operations:
        raise CircuitAnalysisError(
            "Unsupported circuit-analysis operation: "
            f"{operation_name}"
        )

    if cancellation_check is not None:
        cancellation_check()

    if operation_name == "ohms_law":
        result = _ohms_law(
            voltage=voltage,
            current=current,
            resistance=resistance,
        )

    elif operation_name == "series_resistance":
        values = _validate_resistance_list(resistances)

        total = 0.0
        for value in values:
            if cancellation_check is not None:
                cancellation_check()
            total += value

        result = {
            "operation": operation_name,
            "result": total,
        }

    elif operation_name == "parallel_resistance":
        values = _validate_resistance_list(resistances)

        reciprocal_sum = 0.0
        for value in values:
            if cancellation_check is not None:
                cancellation_check()
            reciprocal_sum += 1.0 / value

        result = {
            "operation": operation_name,
            "result": 1.0 / reciprocal_sum,
        }

    elif operation_name == "voltage_divider":
        _require_arguments(
            {
                "input_voltage": input_voltage,
                "r1": r1,
                "r2": r2,
            },
            ("input_voltage", "r1", "r2"),
        )

        input_voltage_value = _validate_scalar(
            input_voltage,
            "input_voltage",
        )
        r1_value = _validate_positive(r1, "r1")
        r2_value = _validate_positive(r2, "r2")

        result = {
            "operation": operation_name,
            "output_voltage": (
                input_voltage_value
                * r2_value
                / (r1_value + r2_value)
            ),
        }

    elif operation_name == "current_divider":
        _require_arguments(
            {
                "total_current": total_current,
                "r1": r1,
                "r2": r2,
            },
            ("total_current", "r1", "r2"),
        )

        total_current_value = _validate_scalar(
            total_current,
            "total_current",
        )
        r1_value = _validate_positive(r1, "r1")
        r2_value = _validate_positive(r2, "r2")

        result = {
            "operation": operation_name,
            "current_r1": (
                total_current_value
                * r2_value
                / (r1_value + r2_value)
            ),
            "current_r2": (
                total_current_value
                * r1_value
                / (r1_value + r2_value)
            ),
        }

    elif operation_name == "power":
        result = _power(
            voltage=voltage,
            current=current,
            resistance=resistance,
        )

    elif operation_name == "energy":
        _require_arguments(
            {
                "power": power,
                "time_seconds": time_seconds,
            },
            ("power", "time_seconds"),
        )

        power_value = _validate_scalar(power, "power")
        time_value = _validate_nonnegative(
            time_seconds,
            "time_seconds",
        )

        result = {
            "operation": operation_name,
            "energy_joules": power_value * time_value,
        }

    elif operation_name == "rc_time_constant":
        _require_arguments(
            {
                "resistance_ohms": resistance_ohms,
                "capacitance_farads": capacitance_farads,
            },
            ("resistance_ohms", "capacitance_farads"),
        )

        resistance_value = _validate_positive(
            resistance_ohms,
            "resistance_ohms",
        )
        capacitance_value = _validate_positive(
            capacitance_farads,
            "capacitance_farads",
        )

        result = {
            "operation": operation_name,
            "time_constant_seconds": (
                resistance_value * capacitance_value
            ),
        }

    else:
        _require_arguments(
            {
                "inductance_henries": inductance_henries,
                "resistance_ohms": resistance_ohms,
            },
            ("inductance_henries", "resistance_ohms"),
        )

        inductance_value = _validate_positive(
            inductance_henries,
            "inductance_henries",
        )
        resistance_value = _validate_positive(
            resistance_ohms,
            "resistance_ohms",
        )

        result = {
            "operation": operation_name,
            "time_constant_seconds": (
                inductance_value / resistance_value
            ),
        }

    if cancellation_check is not None:
        cancellation_check()

    return result


def circuit_analysis_handler(
    context: Any,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Runtime tool handler for circuit analysis."""

    if hasattr(context, "raise_if_cancelled"):
        context.raise_if_cancelled()

    operation = str(arguments.get("operation", ""))

    operation_arguments = {
        key: value
        for key, value in arguments.items()
        if key != "operation"
    }

    result = circuit_analysis(
        operation,
        **operation_arguments,
        cancellation_check=(
            context.raise_if_cancelled
            if hasattr(context, "raise_if_cancelled")
            else None
        ),
    )

    if hasattr(context, "raise_if_cancelled"):
        context.raise_if_cancelled()

    return result
