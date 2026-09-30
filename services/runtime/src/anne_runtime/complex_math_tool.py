from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from .tool_contracts import ToolExecutionError


MAX_ABSOLUTE_VALUE = 1e100


class ComplexMathError(ToolExecutionError):
    """Raised when complex-number inputs or operations are invalid."""


def _validate_component(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ComplexMathError(f"{name} must be numeric.")

    value = float(value)

    if not math.isfinite(value):
        raise ComplexMathError(f"{name} must be finite.")

    if abs(value) > MAX_ABSOLUTE_VALUE:
        raise ComplexMathError(
            f"{name} exceeds the maximum allowed magnitude."
        )

    return value


def _validate_complex(value: Any, name: str = "complex number") -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise ComplexMathError(f"{name} must be an object.")

    if set(value) != {"real", "imaginary"}:
        raise ComplexMathError(
            f"{name} must contain exactly 'real' and 'imaginary'."
        )

    real = _validate_component(value["real"], f"{name}.real")
    imaginary = _validate_component(
        value["imaginary"],
        f"{name}.imaginary",
    )

    return {
        "real": real,
        "imaginary": imaginary,
    }


def _validate_result(real: float, imaginary: float) -> dict[str, float]:
    real = _validate_component(real, "result.real")
    imaginary = _validate_component(imaginary, "result.imaginary")

    return {
        "real": real,
        "imaginary": imaginary,
    }


def _validate_polar_magnitude(value: Any) -> float:
    magnitude = _validate_component(value, "magnitude")

    if magnitude < 0:
        raise ComplexMathError("Polar magnitude cannot be negative.")

    return magnitude


def complex_add(left: Any, right: Any) -> dict[str, float]:
    left = _validate_complex(left, "left")
    right = _validate_complex(right, "right")

    return _validate_result(
        left["real"] + right["real"],
        left["imaginary"] + right["imaginary"],
    )


def complex_subtract(left: Any, right: Any) -> dict[str, float]:
    left = _validate_complex(left, "left")
    right = _validate_complex(right, "right")

    return _validate_result(
        left["real"] - right["real"],
        left["imaginary"] - right["imaginary"],
    )


def complex_multiply(left: Any, right: Any) -> dict[str, float]:
    left = _validate_complex(left, "left")
    right = _validate_complex(right, "right")

    real = (
        left["real"] * right["real"]
        - left["imaginary"] * right["imaginary"]
    )
    imaginary = (
        left["real"] * right["imaginary"]
        + left["imaginary"] * right["real"]
    )

    return _validate_result(real, imaginary)


def complex_divide(left: Any, right: Any) -> dict[str, float]:
    left = _validate_complex(left, "left")
    right = _validate_complex(right, "right")

    denominator = right["real"] ** 2 + right["imaginary"] ** 2

    if denominator == 0:
        raise ComplexMathError("Cannot divide by zero complex number.")

    real = (
        left["real"] * right["real"]
        + left["imaginary"] * right["imaginary"]
    ) / denominator
    imaginary = (
        left["imaginary"] * right["real"]
        - left["real"] * right["imaginary"]
    ) / denominator

    return _validate_result(real, imaginary)


def complex_magnitude(value: Any) -> float:
    value = _validate_complex(value)

    result = math.hypot(value["real"], value["imaginary"])

    return _validate_component(result, "magnitude")


def complex_phase(value: Any) -> float:
    value = _validate_complex(value)

    return math.atan2(value["imaginary"], value["real"])


def complex_conjugate(value: Any) -> dict[str, float]:
    value = _validate_complex(value)

    return _validate_result(
        value["real"],
        -value["imaginary"],
    )


def complex_real(value: Any) -> float:
    return _validate_complex(value)["real"]


def complex_imaginary(value: Any) -> float:
    return _validate_complex(value)["imaginary"]


def complex_to_polar(value: Any) -> dict[str, float]:
    value = _validate_complex(value)

    return {
        "magnitude": complex_magnitude(value),
        "phase": complex_phase(value),
    }


def polar_to_complex(
    *,
    magnitude: Any,
    phase: Any,
) -> dict[str, float]:
    magnitude = _validate_polar_magnitude(magnitude)
    phase = _validate_component(phase, "phase")

    return _validate_result(
        magnitude * math.cos(phase),
        magnitude * math.sin(phase),
    )


def complex_math(
    operation: str,
    *,
    value: Any = None,
    left: Any = None,
    right: Any = None,
    magnitude: Any = None,
    phase: Any = None,
) -> dict[str, Any]:
    if not isinstance(operation, str) or not operation.strip():
        raise ComplexMathError("Operation must be a non-empty string.")

    operation_name = operation.strip().lower()

    if operation_name == "add":
        result = complex_add(left, right)
    elif operation_name == "subtract":
        result = complex_subtract(left, right)
    elif operation_name == "multiply":
        result = complex_multiply(left, right)
    elif operation_name == "divide":
        result = complex_divide(left, right)
    elif operation_name == "magnitude":
        result = complex_magnitude(value)
    elif operation_name == "phase":
        result = complex_phase(value)
    elif operation_name == "conjugate":
        result = complex_conjugate(value)
    elif operation_name == "real":
        result = complex_real(value)
    elif operation_name == "imaginary":
        result = complex_imaginary(value)
    elif operation_name in {"to_polar", "rectangular_to_polar"}:
        result = complex_to_polar(value)
    elif operation_name in {"from_polar", "polar_to_rectangular"}:
        result = polar_to_complex(
            magnitude=magnitude,
            phase=phase,
        )
    else:
        raise ComplexMathError(
            f"Unsupported complex-math operation: {operation_name}"
        )

    return {
        "operation": operation_name,
        "result": result,
    }


def complex_math_handler(context: Any, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    if context.is_cancelled():
        raise ComplexMathError("Complex-math operation was cancelled.")

    return complex_math(
        arguments["operation"],
        value=arguments.get("value"),
        left=arguments.get("left"),
        right=arguments.get("right"),
        magnitude=arguments.get("magnitude"),
        phase=arguments.get("phase"),
    )
