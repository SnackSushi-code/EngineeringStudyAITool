"""Safe deterministic engineering statics calculations."""

from __future__ import annotations

import math
from typing import Any

from .tool_contracts import ToolExecutionError


MAX_ABSOLUTE_VALUE = 1e100
EQUILIBRIUM_TOLERANCE = 1e-9


class StaticsError(ToolExecutionError):
    """Raised when a statics calculation is invalid or unsafe."""


def _require_number(
    arguments: dict[str, Any],
    name: str,
    *,
    non_negative: bool = False,
) -> float:
    if name not in arguments:
        raise StaticsError(f"Missing required argument: {name}.")

    value = arguments[name]

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StaticsError(f"{name} must be a number.")

    value = float(value)

    if not math.isfinite(value):
        raise StaticsError(f"{name} must be finite.")

    if abs(value) > MAX_ABSOLUTE_VALUE:
        raise StaticsError(
            f"{name} exceeds the maximum supported magnitude."
        )

    if non_negative and value < 0:
        raise StaticsError(f"{name} must be non-negative.")

    return value


def _validate_result(value: float) -> float:
    if not math.isfinite(value):
        raise StaticsError("Calculation result must be finite.")

    if abs(value) > MAX_ABSOLUTE_VALUE:
        raise StaticsError(
            "Calculation result exceeds the maximum supported magnitude."
        )

    return float(value)


def _validate_angle(arguments: dict[str, Any]) -> float:
    return _require_number(arguments, "angle_degrees")


def statics(
    operation: str,
    **arguments: Any,
) -> dict[str, Any]:
    """Perform deterministic engineering statics calculations."""

    if not isinstance(operation, str) or not operation.strip():
        raise StaticsError("Statics operation cannot be empty.")

    operation = operation.strip().lower()

    if operation == "force_components":
        magnitude = _require_number(
            arguments,
            "magnitude",
            non_negative=True,
        )
        angle_degrees = _validate_angle(arguments)

        angle_radians = math.radians(angle_degrees)

        fx = _validate_result(
            magnitude * math.cos(angle_radians)
        )
        fy = _validate_result(
            magnitude * math.sin(angle_radians)
        )

        return {
            "operation": operation,
            "fx": fx,
            "fy": fy,
        }

    elif operation == "resultant_force":
        fx = _require_number(arguments, "fx")
        fy = _require_number(arguments, "fy")

        resultant = _validate_result(
            math.hypot(fx, fy)
        )

        return {
            "operation": operation,
            "resultant": resultant,
        }

    elif operation == "resultant_angle":
        fx = _require_number(arguments, "fx")
        fy = _require_number(arguments, "fy")

        if fx == 0.0 and fy == 0.0:
            raise StaticsError(
                "resultant angle is undefined for a zero force vector."
            )

        angle_degrees = _validate_result(
            math.degrees(math.atan2(fy, fx))
        )

        return {
            "operation": operation,
            "angle_degrees": angle_degrees,
        }

    elif operation == "moment_2d":
        x = _require_number(arguments, "x")
        y = _require_number(arguments, "y")
        fx = _require_number(arguments, "fx")
        fy = _require_number(arguments, "fy")

        moment = _validate_result(
            x * fy - y * fx
        )

        return {
            "operation": operation,
            "moment": moment,
        }

    elif operation == "moment_from_force":
        force = _require_number(
            arguments,
            "force",
            non_negative=True,
        )
        perpendicular_distance = _require_number(
            arguments,
            "perpendicular_distance",
            non_negative=True,
        )
        angle_degrees = _validate_angle(arguments)

        angle_radians = math.radians(angle_degrees)

        moment = _validate_result(
            force
            * perpendicular_distance
            * math.sin(angle_radians)
        )

        return {
            "operation": operation,
            "moment": moment,
        }

    elif operation == "equilibrium_force":
        fx_sum = _require_number(arguments, "fx_sum")
        fy_sum = _require_number(arguments, "fy_sum")

        fx = _validate_result(-fx_sum)
        fy = _validate_result(-fy_sum)

        return {
            "operation": operation,
            "fx": fx,
            "fy": fy,
        }

    elif operation == "equilibrium_check":
        fx_sum = _require_number(arguments, "fx_sum")
        fy_sum = _require_number(arguments, "fy_sum")
        moment_sum = _require_number(arguments, "moment_sum")

        force_equilibrium = (
            abs(fx_sum) <= EQUILIBRIUM_TOLERANCE
            and abs(fy_sum) <= EQUILIBRIUM_TOLERANCE
        )

        moment_equilibrium = (
            abs(moment_sum) <= EQUILIBRIUM_TOLERANCE
        )

        return {
            "operation": operation,
            "equilibrium": (
                force_equilibrium and moment_equilibrium
            ),
            "force_equilibrium": force_equilibrium,
            "moment_equilibrium": moment_equilibrium,
        }

    else:
        raise StaticsError(
            f"Unsupported statics operation: {operation}"
        )


def statics_handler(
    context: Any,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Runtime tool handler for deterministic engineering statics."""

    if hasattr(context, "raise_if_cancelled"):
        context.raise_if_cancelled()

    operation = str(arguments.get("operation", ""))

    operation_arguments = {
        key: value
        for key, value in arguments.items()
        if key != "operation"
    }

    result = statics(
        operation,
        **operation_arguments,
    )

    if hasattr(context, "raise_if_cancelled"):
        context.raise_if_cancelled()

    return result
