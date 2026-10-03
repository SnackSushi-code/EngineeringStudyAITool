"""Safe deterministic engineering dynamics calculations."""

from __future__ import annotations

import math
from typing import Any

from .tool_contracts import ToolExecutionError


DEFAULT_GRAVITY = 9.80665
MAX_ABSOLUTE_VALUE = 1e100


class DynamicsError(ToolExecutionError):
    """Raised when a dynamics calculation cannot be performed safely."""


def _require_number(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DynamicsError(f"{name} must be a number.")

    value = float(value)

    if not math.isfinite(value):
        raise DynamicsError(f"{name} must be finite.")

    if abs(value) > MAX_ABSOLUTE_VALUE:
        raise DynamicsError(f"{name} is outside the supported range.")

    return value


def _require_nonnegative(name: str, value: Any) -> float:
    value = _require_number(name, value)

    if value < 0:
        raise DynamicsError(f"{name} cannot be negative.")

    return value


def _require_positive(name: str, value: Any) -> float:
    value = _require_number(name, value)

    if value <= 0:
        raise DynamicsError(f"{name} must be greater than zero.")

    return value


def _optional_gravity(value: Any) -> float:
    if value is None:
        return DEFAULT_GRAVITY

    gravity = _require_number("gravity", value)

    if gravity <= 0:
        raise DynamicsError("gravity must be greater than zero.")

    return gravity


def _validate_result(result: float) -> float:
    if not math.isfinite(result):
        raise DynamicsError("Calculation result must be finite.")

    if abs(result) > MAX_ABSOLUTE_VALUE:
        raise DynamicsError("Calculation result is outside the supported range.")

    return result


def dynamics(operation: str, **kwargs: Any) -> dict[str, Any]:
    """Perform a deterministic engineering dynamics calculation."""

    if not isinstance(operation, str) or not operation.strip():
        raise DynamicsError("operation must be a non-empty string.")

    operation = operation.strip().lower()

    if operation == "force":
        mass = _require_nonnegative("mass", kwargs.get("mass"))
        acceleration = _require_number(
            "acceleration",
            kwargs.get("acceleration"),
        )
        result = _validate_result(mass * acceleration)

    elif operation == "mass_from_force":
        force = _require_number("force", kwargs.get("force"))
        acceleration = _require_positive(
            "acceleration",
            kwargs.get("acceleration"),
        )
        result = _validate_result(force / acceleration)

    elif operation == "acceleration_from_force":
        force = _require_number("force", kwargs.get("force"))
        mass = _require_positive("mass", kwargs.get("mass"))
        result = _validate_result(force / mass)

    elif operation == "weight":
        mass = _require_nonnegative("mass", kwargs.get("mass"))
        gravity = _optional_gravity(kwargs.get("gravity"))
        result = _validate_result(mass * gravity)

    elif operation == "momentum":
        mass = _require_nonnegative("mass", kwargs.get("mass"))
        velocity = _require_number("velocity", kwargs.get("velocity"))
        result = _validate_result(mass * velocity)

    elif operation == "kinetic_energy":
        mass = _require_nonnegative("mass", kwargs.get("mass"))
        velocity = _require_number("velocity", kwargs.get("velocity"))
        result = _validate_result(0.5 * mass * velocity**2)

    elif operation == "potential_energy":
        mass = _require_nonnegative("mass", kwargs.get("mass"))
        height = _require_number("height", kwargs.get("height"))
        gravity = _optional_gravity(kwargs.get("gravity"))
        result = _validate_result(mass * gravity * height)

    elif operation == "work":
        force = _require_number("force", kwargs.get("force"))
        displacement = _require_number(
            "displacement",
            kwargs.get("displacement"),
        )
        angle_degrees = _require_number(
            "angle_degrees",
            kwargs.get("angle_degrees"),
        )

        if not 0.0 <= angle_degrees <= 180.0:
            raise DynamicsError(
                "angle_degrees must be between 0 and 180 degrees."
            )

        result = _validate_result(
            force
            * displacement
            * math.cos(math.radians(angle_degrees))
        )

    elif operation == "power":
        work = _require_number("work", kwargs.get("work"))
        time = _require_positive("time", kwargs.get("time"))
        result = _validate_result(work / time)

    else:
        raise DynamicsError(
            f"Unsupported dynamics operation: {operation}"
        )

    return {
        "operation": operation,
        "result": result,
    }


def dynamics_handler(context: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    """Runtime tool handler for deterministic dynamics calculations."""

    if context.is_cancelled():
        raise DynamicsError("Operation cancelled.")

    operation = arguments.get("operation")
    calculation_arguments = {
        key: value
        for key, value in arguments.items()
        if key != "operation"
    }

    result = dynamics(operation, **calculation_arguments)

    if context.is_cancelled():
        raise DynamicsError("Operation cancelled.")

    return result
