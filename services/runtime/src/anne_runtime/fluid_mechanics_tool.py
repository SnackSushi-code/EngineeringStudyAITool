"""Safe deterministic engineering fluid mechanics calculations."""

from __future__ import annotations

import math
from typing import Any

from .tool_contracts import ToolExecutionError


DEFAULT_GRAVITY = 9.80665
MAX_ABSOLUTE_VALUE = 1e100


class FluidMechanicsError(ToolExecutionError):
    """Raised when a fluid mechanics calculation is invalid or unsafe."""


def _require_number(
    arguments: dict[str, Any],
    name: str,
    *,
    positive: bool = False,
    non_negative: bool = False,
) -> float:
    if name not in arguments:
        raise FluidMechanicsError(
            f"Missing required argument: {name}."
        )

    value = arguments[name]

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FluidMechanicsError(
            f"{name} must be a number."
        )

    value = float(value)

    if not math.isfinite(value):
        raise FluidMechanicsError(
            f"{name} must be finite."
        )

    if abs(value) > MAX_ABSOLUTE_VALUE:
        raise FluidMechanicsError(
            f"{name} exceeds the maximum supported magnitude."
        )

    if positive and value <= 0:
        raise FluidMechanicsError(
            f"{name} must be positive."
        )

    if non_negative and value < 0:
        raise FluidMechanicsError(
            f"{name} must be non-negative."
        )

    return value


def _validate_result(value: float) -> float:
    if not math.isfinite(value):
        raise FluidMechanicsError(
            "Calculation result must be finite."
        )

    if abs(value) > MAX_ABSOLUTE_VALUE:
        raise FluidMechanicsError(
            "Calculation result exceeds the maximum supported magnitude."
        )

    return float(value)


def fluid_mechanics(
    operation: str,
    **arguments: Any,
) -> dict[str, Any]:
    """Perform deterministic engineering fluid mechanics calculations."""

    if not isinstance(operation, str) or not operation.strip():
        raise FluidMechanicsError(
            "Fluid mechanics operation cannot be empty."
        )

    operation = operation.strip().lower()

    if operation == "pressure":
        force = _require_number(arguments, "force")
        area = _require_number(
            arguments,
            "area",
            positive=True,
        )

        pressure = _validate_result(force / area)

        return {
            "operation": operation,
            "pressure": pressure,
        }

    elif operation == "hydrostatic_pressure":
        density = _require_number(
            arguments,
            "density",
            non_negative=True,
        )
        gravity = _require_number(
            arguments,
            "gravity",
            positive=True,
        )
        depth = _require_number(
            arguments,
            "depth",
            non_negative=True,
        )

        pressure = _validate_result(
            density * gravity * depth
        )

        return {
            "operation": operation,
            "pressure": pressure,
        }

    elif operation == "absolute_pressure":
        gauge_pressure = _require_number(
            arguments,
            "gauge_pressure",
        )
        atmospheric_pressure = _require_number(
            arguments,
            "atmospheric_pressure",
            non_negative=True,
        )

        pressure = _validate_result(
            gauge_pressure + atmospheric_pressure
        )

        return {
            "operation": operation,
            "pressure": pressure,
        }

    elif operation == "gauge_pressure":
        absolute_pressure = _require_number(
            arguments,
            "absolute_pressure",
        )
        atmospheric_pressure = _require_number(
            arguments,
            "atmospheric_pressure",
            non_negative=True,
        )

        pressure = _validate_result(
            absolute_pressure - atmospheric_pressure
        )

        return {
            "operation": operation,
            "pressure": pressure,
        }

    elif operation == "density":
        mass = _require_number(
            arguments,
            "mass",
            non_negative=True,
        )
        volume = _require_number(
            arguments,
            "volume",
            positive=True,
        )

        density = _validate_result(mass / volume)

        return {
            "operation": operation,
            "density": density,
        }

    elif operation == "specific_weight":
        density = _require_number(
            arguments,
            "density",
            non_negative=True,
        )
        gravity = _require_number(
            arguments,
            "gravity",
            positive=True,
        )

        specific_weight = _validate_result(
            density * gravity
        )

        return {
            "operation": operation,
            "specific_weight": specific_weight,
        }

    elif operation == "continuity":
        area_1 = _require_number(
            arguments,
            "area_1",
            positive=True,
        )
        velocity_1 = _require_number(
            arguments,
            "velocity_1",
        )
        area_2 = _require_number(
            arguments,
            "area_2",
            positive=True,
        )

        velocity_2 = _validate_result(
            area_1 * velocity_1 / area_2
        )

        return {
            "operation": operation,
            "velocity_2": velocity_2,
        }

    elif operation == "volumetric_flow_rate":
        area = _require_number(
            arguments,
            "area",
            positive=True,
        )
        velocity = _require_number(
            arguments,
            "velocity",
        )

        flow_rate = _validate_result(
            area * velocity
        )

        return {
            "operation": operation,
            "flow_rate": flow_rate,
        }

    elif operation == "mass_flow_rate":
        density = _require_number(
            arguments,
            "density",
            non_negative=True,
        )
        volumetric_flow_rate = _require_number(
            arguments,
            "volumetric_flow_rate",
        )

        mass_flow_rate = _validate_result(
            density * volumetric_flow_rate
        )

        return {
            "operation": operation,
            "mass_flow_rate": mass_flow_rate,
        }

    elif operation == "dynamic_pressure":
        density = _require_number(
            arguments,
            "density",
            non_negative=True,
        )
        velocity = _require_number(
            arguments,
            "velocity",
        )

        dynamic_pressure = _validate_result(
            0.5 * density * velocity**2
        )

        return {
            "operation": operation,
            "dynamic_pressure": dynamic_pressure,
        }

    elif operation == "reynolds_number":
        density = _require_number(
            arguments,
            "density",
            non_negative=True,
        )
        velocity = _require_number(
            arguments,
            "velocity",
        )
        characteristic_length = _require_number(
            arguments,
            "characteristic_length",
            positive=True,
        )
        dynamic_viscosity = _require_number(
            arguments,
            "dynamic_viscosity",
            positive=True,
        )

        reynolds_number = _validate_result(
            density
            * velocity
            * characteristic_length
            / dynamic_viscosity
        )

        return {
            "operation": operation,
            "reynolds_number": reynolds_number,
        }

    elif operation == "hydraulic_power":
        density = _require_number(
            arguments,
            "density",
            non_negative=True,
        )
        gravity = _require_number(
            arguments,
            "gravity",
            positive=True,
        )
        volumetric_flow_rate = _require_number(
            arguments,
            "volumetric_flow_rate",
            non_negative=True,
        )
        head = _require_number(
            arguments,
            "head",
            non_negative=True,
        )

        power = _validate_result(
            density
            * gravity
            * volumetric_flow_rate
            * head
        )

        return {
            "operation": operation,
            "power": power,
        }

    elif operation == "buoyant_force":
        density = _require_number(
            arguments,
            "density",
            non_negative=True,
        )
        gravity = _require_number(
            arguments,
            "gravity",
            positive=True,
        )
        displaced_volume = _require_number(
            arguments,
            "displaced_volume",
            non_negative=True,
        )

        buoyant_force = _validate_result(
            density
            * gravity
            * displaced_volume
        )

        return {
            "operation": operation,
            "buoyant_force": buoyant_force,
        }

    elif operation == "bernoulli_velocity":
        pressure_1 = _require_number(
            arguments,
            "pressure_1",
        )
        pressure_2 = _require_number(
            arguments,
            "pressure_2",
        )
        density = _require_number(
            arguments,
            "density",
            positive=True,
        )
        velocity_1 = _require_number(
            arguments,
            "velocity_1",
        )
        elevation_1 = _require_number(
            arguments,
            "elevation_1",
        )
        elevation_2 = _require_number(
            arguments,
            "elevation_2",
        )
        gravity = _require_number(
            arguments,
            "gravity",
            positive=True,
        )

        velocity_squared = (
            velocity_1**2
            + 2.0
            * (
                (pressure_1 - pressure_2) / density
                + gravity * (elevation_1 - elevation_2)
            )
        )

        if velocity_squared < 0:
            raise FluidMechanicsError(
                "Calculated velocity squared cannot be negative."
            )

        velocity_2 = _validate_result(
            math.sqrt(velocity_squared)
        )

        return {
            "operation": operation,
            "velocity_2": velocity_2,
        }

    else:
        raise FluidMechanicsError(
            f"Unsupported fluid mechanics operation: {operation}"
        )


def fluid_mechanics_handler(
    context: Any,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Runtime handler for deterministic fluid mechanics calculations."""

    if hasattr(context, "raise_if_cancelled"):
        context.raise_if_cancelled()

    operation = str(arguments.get("operation", ""))

    operation_arguments = {
        key: value
        for key, value in arguments.items()
        if key != "operation"
    }

    result = fluid_mechanics(
        operation,
        **operation_arguments,
    )

    if hasattr(context, "raise_if_cancelled"):
        context.raise_if_cancelled()

    return result
