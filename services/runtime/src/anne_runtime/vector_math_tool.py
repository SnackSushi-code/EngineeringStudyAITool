from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from .tool_contracts import ToolExecutionError


MAX_VECTOR_LENGTH = 64
MAX_ABSOLUTE_VALUE = 1e100
MAX_RESULT_COMPONENTS = 64


class VectorMathError(ToolExecutionError):
    """Raised when a vector-math operation is invalid or unsafe."""


def _validate_vector(value: Any, name: str) -> tuple[float, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise VectorMathError(f"{name} must be a numeric vector.")

    if len(value) == 0:
        raise VectorMathError(f"{name} must not be empty.")

    if len(value) > MAX_VECTOR_LENGTH:
        raise VectorMathError(
            f"{name} exceeds the maximum vector length of {MAX_VECTOR_LENGTH}."
        )

    result: list[float] = []

    for index, component in enumerate(value):
        if isinstance(component, bool) or not isinstance(component, (int, float)):
            raise VectorMathError(
                f"{name}[{index}] must be a finite numeric value."
            )

        number = float(component)

        if not math.isfinite(number):
            raise VectorMathError(
                f"{name}[{index}] must be a finite numeric value."
            )

        if abs(number) > MAX_ABSOLUTE_VALUE:
            raise VectorMathError(
                f"{name}[{index}] exceeds the maximum supported magnitude."
            )

        result.append(number)

    return tuple(result)


def _validate_scalar(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise VectorMathError("scalar must be a finite numeric value.")

    scalar = float(value)

    if not math.isfinite(scalar):
        raise VectorMathError("scalar must be a finite numeric value.")

    if abs(scalar) > MAX_ABSOLUTE_VALUE:
        raise VectorMathError("scalar exceeds the maximum supported magnitude.")

    return scalar


def _validate_result(values: Any) -> tuple[float, ...]:
    result = tuple(float(value) for value in values)

    if len(result) > MAX_RESULT_COMPONENTS:
        raise VectorMathError("Result exceeds the maximum component count.")

    for value in result:
        if not math.isfinite(value):
            raise VectorMathError("Vector result must contain finite values.")

        if abs(value) > MAX_ABSOLUTE_VALUE:
            raise VectorMathError(
                "Vector result exceeds the maximum supported magnitude."
            )

    return result


def _require_same_dimension(
    left: tuple[float, ...],
    right: tuple[float, ...],
) -> None:
    if len(left) != len(right):
        raise VectorMathError(
            f"Vector dimensions must match: {len(left)} != {len(right)}."
        )


def vector_magnitude(vector: Any) -> float:
    values = _validate_vector(vector, "vector")

    try:
        result = math.sqrt(math.fsum(value * value for value in values))
    except (ArithmeticError, OverflowError) as exc:
        raise VectorMathError("Vector magnitude calculation failed.") from exc

    if not math.isfinite(result):
        raise VectorMathError("Vector magnitude must be finite.")

    return result


def vector_add(left: Any, right: Any) -> tuple[float, ...]:
    left_values = _validate_vector(left, "left")
    right_values = _validate_vector(right, "right")
    _require_same_dimension(left_values, right_values)

    return _validate_result(
        left_value + right_value
        for left_value, right_value in zip(left_values, right_values)
    )


def vector_subtract(left: Any, right: Any) -> tuple[float, ...]:
    left_values = _validate_vector(left, "left")
    right_values = _validate_vector(right, "right")
    _require_same_dimension(left_values, right_values)

    return _validate_result(
        left_value - right_value
        for left_value, right_value in zip(left_values, right_values)
    )


def vector_scale(vector: Any, scalar: Any) -> tuple[float, ...]:
    values = _validate_vector(vector, "vector")
    scale = _validate_scalar(scalar)

    return _validate_result(value * scale for value in values)


def vector_dot(left: Any, right: Any) -> float:
    left_values = _validate_vector(left, "left")
    right_values = _validate_vector(right, "right")
    _require_same_dimension(left_values, right_values)

    try:
        result = math.fsum(
            left_value * right_value
            for left_value, right_value in zip(left_values, right_values)
        )
    except (ArithmeticError, OverflowError) as exc:
        raise VectorMathError("Vector dot-product calculation failed.") from exc

    if not math.isfinite(result):
        raise VectorMathError("Vector dot-product result must be finite.")

    if abs(result) > MAX_ABSOLUTE_VALUE:
        raise VectorMathError(
            "Vector dot-product result exceeds the maximum supported magnitude."
        )

    return result


def vector_cross(left: Any, right: Any) -> tuple[float, ...]:
    left_values = _validate_vector(left, "left")
    right_values = _validate_vector(right, "right")

    if len(left_values) != 3 or len(right_values) != 3:
        raise VectorMathError(
            "Cross product requires two 3-dimensional vectors."
        )

    result = (
        left_values[1] * right_values[2]
        - left_values[2] * right_values[1],
        left_values[2] * right_values[0]
        - left_values[0] * right_values[2],
        left_values[0] * right_values[1]
        - left_values[1] * right_values[0],
    )

    return _validate_result(result)


def vector_normalize(vector: Any) -> tuple[float, ...]:
    values = _validate_vector(vector, "vector")
    magnitude = vector_magnitude(values)

    if magnitude == 0:
        raise VectorMathError("Zero vector cannot be normalized.")

    return _validate_result(value / magnitude for value in values)


def vector_angle(left: Any, right: Any) -> float:
    left_values = _validate_vector(left, "left")
    right_values = _validate_vector(right, "right")
    _require_same_dimension(left_values, right_values)

    left_magnitude = vector_magnitude(left_values)
    right_magnitude = vector_magnitude(right_values)

    if left_magnitude == 0 or right_magnitude == 0:
        raise VectorMathError("Cannot calculate an angle involving a zero vector.")

    dot = vector_dot(left_values, right_values)
    denominator = left_magnitude * right_magnitude

    if not math.isfinite(denominator) or denominator == 0:
        raise VectorMathError("Vector angle calculation failed.")

    cosine = max(-1.0, min(1.0, dot / denominator))
    result = math.acos(cosine)

    if not math.isfinite(result):
        raise VectorMathError("Vector angle result must be finite.")

    return result


def vector_math(
    operation: Any,
    *,
    vector: Any = None,
    left: Any = None,
    right: Any = None,
    scalar: Any = None,
) -> Mapping[str, Any]:
    """Dispatch a supported deterministic vector-math operation."""
    if not isinstance(operation, str):
        raise VectorMathError("Vector-math operation must be a non-empty string.")

    operation_name = operation.strip().lower()

    if not operation_name:
        raise VectorMathError("Vector-math operation must be a non-empty string.")

    if operation_name == "magnitude":
        result = vector_magnitude(vector)
    elif operation_name == "add":
        result = vector_add(left, right)
    elif operation_name == "subtract":
        result = vector_subtract(left, right)
    elif operation_name == "scale":
        result = vector_scale(vector, scalar)
    elif operation_name == "dot":
        result = vector_dot(left, right)
    elif operation_name == "cross":
        result = vector_cross(left, right)
    elif operation_name == "normalize":
        result = vector_normalize(vector)
    elif operation_name == "angle":
        result = vector_angle(left, right)
    else:
        raise VectorMathError(
            f"Unsupported vector operation: {operation_name}."
        )

    return {
        "operation": operation_name,
        "result": result,
    }


def vector_math_handler(
    context: Any,
    arguments: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Tool handler for Ann-E deterministic vector mathematics."""
    if context.is_cancelled():
        context.raise_if_cancelled()

    return vector_math(
        arguments.get("operation"),
        vector=arguments.get("vector"),
        left=arguments.get("left"),
        right=arguments.get("right"),
        scalar=arguments.get("scalar"),
    )
