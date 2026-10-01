from __future__ import annotations

import math
from typing import Any

from .tool_contracts import ToolExecutionError


DEFAULT_GRAVITY = 9.80665
MAX_ABSOLUTE_VALUE = 1e100


class KinematicsError(ToolExecutionError):
    """Raised when a kinematics calculation is invalid or unsafe."""


def _require_number(
    arguments: dict[str, Any],
    name: str,
    *,
    non_negative: bool = False,
    positive: bool = False,
) -> float:
    if name not in arguments:
        raise KinematicsError(f"Missing required argument: {name}.")

    value = arguments[name]

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise KinematicsError(f"{name} must be a number.")

    value = float(value)

    if not math.isfinite(value):
        raise KinematicsError(f"{name} must be finite.")

    if abs(value) > MAX_ABSOLUTE_VALUE:
        raise KinematicsError(
            f"{name} exceeds the maximum supported magnitude."
        )

    if positive and value <= 0:
        raise KinematicsError(f"{name} must be positive.")

    if non_negative and value < 0:
        raise KinematicsError(f"{name} must be non-negative.")

    return value


def _optional_gravity(arguments: dict[str, Any]) -> float:
    if "gravity" not in arguments:
        return DEFAULT_GRAVITY

    gravity = _require_number(
        arguments,
        "gravity",
        positive=True,
    )

    return gravity


def _validate_result(value: float) -> float:
    if not math.isfinite(value):
        raise KinematicsError("Calculation result must be finite.")

    if abs(value) > MAX_ABSOLUTE_VALUE:
        raise KinematicsError(
            "Calculation result exceeds the maximum supported magnitude."
        )

    return value


def kinematics(
    operation: str,
    **arguments: Any,
) -> dict[str, Any]:
    """Perform deterministic engineering kinematics calculations."""

    if not isinstance(operation, str) or not operation.strip():
        raise KinematicsError("Kinematics operation cannot be empty.")

    operation = operation.strip().lower()

    if operation == "velocity":
        initial_velocity = _require_number(arguments, "initial_velocity")
        acceleration = _require_number(arguments, "acceleration")
        time = _require_number(arguments, "time")

        result = initial_velocity + acceleration * time

    elif operation == "displacement":
        initial_velocity = _require_number(arguments, "initial_velocity")
        acceleration = _require_number(arguments, "acceleration")
        time = _require_number(arguments, "time")

        result = (
            initial_velocity * time
            + 0.5 * acceleration * time**2
        )

    elif operation == "final_velocity_from_displacement":
        initial_velocity = _require_number(arguments, "initial_velocity")
        acceleration = _require_number(arguments, "acceleration")
        displacement = _require_number(arguments, "displacement")

        radicand = (
            initial_velocity**2
            + 2.0 * acceleration * displacement
        )

        if radicand < 0:
            raise KinematicsError(
                "The velocity equation has no real-valued solution."
            )

        result = math.sqrt(radicand)

    elif operation == "acceleration":
        initial_velocity = _require_number(arguments, "initial_velocity")
        final_velocity = _require_number(arguments, "final_velocity")
        time = _require_number(arguments, "time")

        if time == 0:
            raise KinematicsError(
                "time must not be zero when calculating acceleration."
            )

        result = (final_velocity - initial_velocity) / time

    elif operation == "time_from_velocity":
        initial_velocity = _require_number(arguments, "initial_velocity")
        final_velocity = _require_number(arguments, "final_velocity")
        acceleration = _require_number(arguments, "acceleration")

        if acceleration == 0:
            raise KinematicsError(
                "acceleration must not be zero when calculating time."
            )

        result = (final_velocity - initial_velocity) / acceleration

    elif operation in {
        "projectile_time",
        "projectile_range",
        "projectile_max_height",
    }:
        initial_speed = _require_number(
            arguments,
            "initial_speed",
            non_negative=True,
        )
        launch_angle_degrees = _require_number(
            arguments,
            "launch_angle_degrees",
        )
        gravity = _optional_gravity(arguments)

        if not 0.0 <= launch_angle_degrees <= 90.0:
            raise KinematicsError(
                "launch_angle_degrees must be between 0 and 90 degrees."
            )

        angle_radians = math.radians(launch_angle_degrees)
        vertical_velocity = (
            initial_speed * math.sin(angle_radians)
        )

        if operation == "projectile_time":
            result = (2.0 * vertical_velocity) / gravity

        elif operation == "projectile_range":
            result = (
                initial_speed**2
                * math.sin(2.0 * angle_radians)
                / gravity
            )

        else:
            result = (
                vertical_velocity**2
                / (2.0 * gravity)
            )

    else:
        raise KinematicsError(
            f"Unsupported kinematics operation: {operation}."
        )

    result = _validate_result(float(result))

    return {
        "operation": operation,
        "result": result,
    }


def kinematics_handler(
    context: Any,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Runtime tool handler for deterministic kinematics."""

    if hasattr(context, "raise_if_cancelled"):
        context.raise_if_cancelled()

    operation = str(arguments.get("operation", ""))

    operation_arguments = {
        key: value
        for key, value in arguments.items()
        if key != "operation"
    }

    result = kinematics(
        operation,
        **operation_arguments,
    )

    if hasattr(context, "raise_if_cancelled"):
        context.raise_if_cancelled()

    return result
