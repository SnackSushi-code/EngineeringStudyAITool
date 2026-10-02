from __future__ import annotations

import math
from typing import Any, Mapping

from .tool_contracts import ToolExecutionError


MAX_ABSOLUTE_VALUE = 1e100


class ThermodynamicsError(ToolExecutionError):
    """Raised when a thermodynamics calculation cannot be completed safely."""


def _require_number(
    arguments: Mapping[str, Any],
    name: str,
    *,
    positive: bool = False,
    non_negative: bool = False,
) -> float:
    if name not in arguments:
        raise ThermodynamicsError(
            f"Missing required argument: {name}"
        )

    value = arguments[name]

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ThermodynamicsError(
            f"{name} must be a finite number"
        )

    value = float(value)

    if not math.isfinite(value):
        raise ThermodynamicsError(
            f"{name} must be a finite number"
        )

    if abs(value) > MAX_ABSOLUTE_VALUE:
        raise ThermodynamicsError(
            f"{name} exceeds the supported magnitude limit"
        )

    if positive and value <= 0:
        raise ThermodynamicsError(
            f"{name} must be greater than zero"
        )

    if non_negative and value < 0:
        raise ThermodynamicsError(
            f"{name} must be non-negative"
        )

    return value


def _validate_result(value: float) -> float:
    if not math.isfinite(value):
        raise ThermodynamicsError(
            "Calculation produced a non-finite result"
        )

    if abs(value) > MAX_ABSOLUTE_VALUE:
        raise ThermodynamicsError(
            "Calculation result exceeds the supported magnitude limit"
        )

    return value


def thermodynamics(
    operation: str,
    **arguments: Any,
) -> dict[str, Any]:
    """Perform deterministic engineering thermodynamics calculations."""

    if not isinstance(operation, str) or not operation:
        raise ThermodynamicsError(
            "operation must be a non-empty string"
        )

    if operation == "ideal_gas_pressure":
        moles = _require_number(
            arguments,
            "moles",
            non_negative=True,
        )
        gas_constant = _require_number(
            arguments,
            "gas_constant",
            positive=True,
        )
        temperature = _require_number(
            arguments,
            "temperature",
            positive=True,
        )
        volume = _require_number(
            arguments,
            "volume",
            positive=True,
        )

        pressure = _validate_result(
            moles * gas_constant * temperature / volume
        )

        return {
            "operation": operation,
            "pressure": pressure,
        }

    elif operation == "ideal_gas_volume":
        moles = _require_number(
            arguments,
            "moles",
            non_negative=True,
        )
        gas_constant = _require_number(
            arguments,
            "gas_constant",
            positive=True,
        )
        temperature = _require_number(
            arguments,
            "temperature",
            positive=True,
        )
        pressure = _require_number(
            arguments,
            "pressure",
            positive=True,
        )

        volume = _validate_result(
            moles * gas_constant * temperature / pressure
        )

        return {
            "operation": operation,
            "volume": volume,
        }

    elif operation == "ideal_gas_temperature":
        pressure = _require_number(
            arguments,
            "pressure",
            positive=True,
        )
        volume = _require_number(
            arguments,
            "volume",
            positive=True,
        )
        moles = _require_number(
            arguments,
            "moles",
            non_negative=True,
        )
        gas_constant = _require_number(
            arguments,
            "gas_constant",
            positive=True,
        )

        if moles == 0:
            raise ThermodynamicsError(
                "moles must be greater than zero"
            )

        temperature = _validate_result(
            pressure * volume / (moles * gas_constant)
        )

        if temperature <= 0:
            raise ThermodynamicsError(
                "Calculated temperature must be greater than zero"
            )

        return {
            "operation": operation,
            "temperature": temperature,
        }

    elif operation == "ideal_gas_moles":
        pressure = _require_number(
            arguments,
            "pressure",
            positive=True,
        )
        volume = _require_number(
            arguments,
            "volume",
            positive=True,
        )
        gas_constant = _require_number(
            arguments,
            "gas_constant",
            positive=True,
        )
        temperature = _require_number(
            arguments,
            "temperature",
            positive=True,
        )

        moles = _validate_result(
            pressure * volume / (gas_constant * temperature)
        )

        return {
            "operation": operation,
            "moles": moles,
        }

    elif operation == "density_ideal_gas":
        pressure = _require_number(
            arguments,
            "pressure",
            positive=True,
        )
        molar_mass = _require_number(
            arguments,
            "molar_mass",
            positive=True,
        )
        gas_constant = _require_number(
            arguments,
            "gas_constant",
            positive=True,
        )
        temperature = _require_number(
            arguments,
            "temperature",
            positive=True,
        )

        density = _validate_result(
            pressure * molar_mass / (gas_constant * temperature)
        )

        return {
            "operation": operation,
            "density": density,
        }

    elif operation == "specific_gas_constant":
        universal_gas_constant = _require_number(
            arguments,
            "universal_gas_constant",
            positive=True,
        )
        molar_mass = _require_number(
            arguments,
            "molar_mass",
            positive=True,
        )

        specific_gas_constant = _validate_result(
            universal_gas_constant / molar_mass
        )

        return {
            "operation": operation,
            "specific_gas_constant": specific_gas_constant,
        }

    elif operation == "heat_transfer":
        mass = _require_number(
            arguments,
            "mass",
            non_negative=True,
        )
        specific_heat = _require_number(
            arguments,
            "specific_heat",
            non_negative=True,
        )
        temperature_change = _require_number(
            arguments,
            "temperature_change",
        )

        heat = _validate_result(
            mass * specific_heat * temperature_change
        )

        return {
            "operation": operation,
            "heat": heat,
        }

    elif operation == "sensible_heat":
        mass = _require_number(
            arguments,
            "mass",
            non_negative=True,
        )
        specific_heat_capacity = _require_number(
            arguments,
            "specific_heat_capacity",
            non_negative=True,
        )
        temperature_change = _require_number(
            arguments,
            "temperature_change",
        )

        heat = _validate_result(
            mass
            * specific_heat_capacity
            * temperature_change
        )

        return {
            "operation": operation,
            "heat": heat,
        }

    elif operation == "latent_heat":
        mass = _require_number(
            arguments,
            "mass",
            non_negative=True,
        )
        latent_heat = _require_number(
            arguments,
            "latent_heat",
            non_negative=True,
        )

        heat = _validate_result(
            mass * latent_heat
        )

        return {
            "operation": operation,
            "heat": heat,
        }

    elif operation == "thermal_efficiency":
        work_output = _require_number(
            arguments,
            "work_output",
            non_negative=True,
        )
        heat_input = _require_number(
            arguments,
            "heat_input",
            positive=True,
        )

        efficiency = _validate_result(
            work_output / heat_input
        )

        return {
            "operation": operation,
            "efficiency": efficiency,
        }

    elif operation == "coefficient_of_performance_refrigerator":
        cooling_effect = _require_number(
            arguments,
            "cooling_effect",
            non_negative=True,
        )
        work_input = _require_number(
            arguments,
            "work_input",
            positive=True,
        )

        cop = _validate_result(
            cooling_effect / work_input
        )

        return {
            "operation": operation,
            "cop": cop,
        }

    elif operation == "coefficient_of_performance_heat_pump":
        heating_effect = _require_number(
            arguments,
            "heating_effect",
            non_negative=True,
        )
        work_input = _require_number(
            arguments,
            "work_input",
            positive=True,
        )

        cop = _validate_result(
            heating_effect / work_input
        )

        return {
            "operation": operation,
            "cop": cop,
        }

    elif operation == "first_law_closed_system":
        heat_transfer = _require_number(
            arguments,
            "heat_transfer",
        )
        work_output = _require_number(
            arguments,
            "work_output",
        )

        change_internal_energy = _validate_result(
            heat_transfer - work_output
        )

        return {
            "operation": operation,
            "change_internal_energy": change_internal_energy,
        }

    elif operation == "entropy_change":
        mass = _require_number(
            arguments,
            "mass",
            non_negative=True,
        )
        specific_heat = _require_number(
            arguments,
            "specific_heat",
            positive=True,
        )
        temperature_initial = _require_number(
            arguments,
            "temperature_initial",
            positive=True,
        )
        temperature_final = _require_number(
            arguments,
            "temperature_final",
            positive=True,
        )

        entropy_change = _validate_result(
            mass
            * specific_heat
            * math.log(
                temperature_final / temperature_initial
            )
        )

        return {
            "operation": operation,
            "entropy_change": entropy_change,
        }

    else:
        raise ThermodynamicsError(
            f"Unsupported thermodynamics operation: {operation}"
        )


def thermodynamics_handler(
    context: Any,
    arguments: Mapping[str, Any],
) -> dict[str, Any]:
    """Runtime handler for deterministic thermodynamics calculations."""

    if hasattr(context, "raise_if_cancelled"):
        context.raise_if_cancelled()

    operation = arguments.get("operation", "")

    if not isinstance(operation, str):
        raise ThermodynamicsError(
            "operation must be a string"
        )

    operation_arguments = {
        key: value
        for key, value in arguments.items()
        if key != "operation"
    }

    result = thermodynamics(
        operation,
        **operation_arguments,
    )

    if hasattr(context, "raise_if_cancelled"):
        context.raise_if_cancelled()

    return result
