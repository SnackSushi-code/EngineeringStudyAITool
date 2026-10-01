"""Safe deterministic engineering strength-of-materials calculations."""

from __future__ import annotations

import math
from typing import Any

from .tool_contracts import ToolExecutionError


MAX_ABSOLUTE_VALUE = 1e100


class StrengthOfMaterialsError(ToolExecutionError):
    """Raised when a strength-of-materials calculation is invalid or unsafe."""


def _require_number(
    arguments: dict[str, Any],
    name: str,
    *,
    positive: bool = False,
    non_negative: bool = False,
) -> float:
    if name not in arguments:
        raise StrengthOfMaterialsError(
            f"Missing required argument: {name}."
        )

    value = arguments[name]

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StrengthOfMaterialsError(
            f"Argument '{name}' must be numeric."
        )

    value = float(value)

    if not math.isfinite(value):
        raise StrengthOfMaterialsError(
            f"Argument '{name}' must be finite."
        )

    if abs(value) > MAX_ABSOLUTE_VALUE:
        raise StrengthOfMaterialsError(
            f"Argument '{name}' exceeds the allowed magnitude."
        )

    if positive and value <= 0:
        raise StrengthOfMaterialsError(
            f"Argument '{name}' must be greater than zero."
        )

    if non_negative and value < 0:
        raise StrengthOfMaterialsError(
            f"Argument '{name}' must be non-negative."
        )

    return value


def _validate_result(value: float) -> float:
    if not math.isfinite(value):
        raise StrengthOfMaterialsError(
            "Calculation result must be finite."
        )

    if abs(value) > MAX_ABSOLUTE_VALUE:
        raise StrengthOfMaterialsError(
            "Calculation result exceeds the allowed magnitude."
        )

    return value


def strength_of_materials(
    operation: str,
    **arguments: Any,
) -> dict[str, float | str]:
    """Perform a deterministic strength-of-materials calculation."""

    if not isinstance(operation, str):
        raise StrengthOfMaterialsError(
            "Operation must be a string."
        )

    operation = operation.strip().lower()

    if operation == "normal_stress":
        force = _require_number(arguments, "force")
        area = _require_number(arguments, "area", positive=True)

        stress = _validate_result(force / area)

        return {
            "operation": operation,
            "stress": stress,
        }

    elif operation == "shear_stress":
        force = _require_number(arguments, "force")
        area = _require_number(arguments, "area", positive=True)

        stress = _validate_result(force / area)

        return {
            "operation": operation,
            "stress": stress,
        }

    elif operation == "strain":
        elongation = _require_number(arguments, "elongation")
        original_length = _require_number(
            arguments,
            "original_length",
            positive=True,
        )

        strain = _validate_result(elongation / original_length)

        return {
            "operation": operation,
            "strain": strain,
        }

    elif operation == "elongation":
        force = _require_number(arguments, "force")
        length = _require_number(arguments, "length", positive=True)
        area = _require_number(arguments, "area", positive=True)
        youngs_modulus = _require_number(
            arguments,
            "youngs_modulus",
            positive=True,
        )

        elongation = _validate_result(
            force * length / (area * youngs_modulus)
        )

        return {
            "operation": operation,
            "elongation": elongation,
        }

    elif operation == "hookes_law":
        youngs_modulus = _require_number(
            arguments,
            "youngs_modulus",
            positive=True,
        )
        strain = _require_number(arguments, "strain")

        stress = _validate_result(youngs_modulus * strain)

        return {
            "operation": operation,
            "stress": stress,
        }

    elif operation == "youngs_modulus":
        stress = _require_number(arguments, "stress")
        strain = _require_number(
            arguments,
            "strain",
            positive=True,
        )

        youngs_modulus = _validate_result(stress / strain)

        return {
            "operation": operation,
            "youngs_modulus": youngs_modulus,
        }

    elif operation == "factor_of_safety":
        failure_stress = _require_number(
            arguments,
            "failure_stress",
            non_negative=True,
        )
        working_stress = _require_number(
            arguments,
            "working_stress",
            positive=True,
        )

        factor_of_safety = _validate_result(
            failure_stress / working_stress
        )

        return {
            "operation": operation,
            "factor_of_safety": factor_of_safety,
        }

    elif operation == "thermal_strain":
        coefficient_of_expansion = _require_number(
            arguments,
            "coefficient_of_expansion",
        )
        temperature_change = _require_number(
            arguments,
            "temperature_change",
        )

        strain = _validate_result(
            coefficient_of_expansion * temperature_change
        )

        return {
            "operation": operation,
            "strain": strain,
        }

    elif operation == "thermal_expansion":
        coefficient_of_expansion = _require_number(
            arguments,
            "coefficient_of_expansion",
        )
        length = _require_number(arguments, "length", positive=True)
        temperature_change = _require_number(
            arguments,
            "temperature_change",
        )

        elongation = _validate_result(
            coefficient_of_expansion * length * temperature_change
        )

        return {
            "operation": operation,
            "elongation": elongation,
        }

    elif operation == "bending_stress":
        moment = _require_number(arguments, "moment")
        distance_from_neutral_axis = _require_number(
            arguments,
            "distance_from_neutral_axis",
            non_negative=True,
        )
        area_moment_of_inertia = _require_number(
            arguments,
            "area_moment_of_inertia",
            positive=True,
        )

        stress = _validate_result(
            moment
            * distance_from_neutral_axis
            / area_moment_of_inertia
        )

        return {
            "operation": operation,
            "stress": stress,
        }

    elif operation == "beam_shear_stress":
        shear_force = _require_number(arguments, "shear_force")
        first_moment_area = _require_number(
            arguments,
            "first_moment_area",
            non_negative=True,
        )
        area_moment_of_inertia = _require_number(
            arguments,
            "area_moment_of_inertia",
            positive=True,
        )
        thickness = _require_number(
            arguments,
            "thickness",
            positive=True,
        )

        stress = _validate_result(
            shear_force
            * first_moment_area
            / (area_moment_of_inertia * thickness)
        )

        return {
            "operation": operation,
            "stress": stress,
        }

    else:
        raise StrengthOfMaterialsError(
            f"Unsupported strength-of-materials operation: {operation}."
        )


def strength_of_materials_handler(
    context: Any,
    arguments: dict[str, Any],
) -> dict[str, float | str]:
    """Runtime handler for the strength-of-materials tool."""

    raise_if_cancelled = getattr(context, "raise_if_cancelled", None)

    if callable(raise_if_cancelled):
        raise_if_cancelled()

    operation = arguments.get("operation")

    if operation is None:
        raise StrengthOfMaterialsError(
            "Missing required argument: operation."
        )

    calculation_arguments = dict(arguments)
    calculation_arguments.pop("operation", None)

    result = strength_of_materials(
        operation,
        **calculation_arguments,
    )

    if callable(raise_if_cancelled):
        raise_if_cancelled()

    return result
