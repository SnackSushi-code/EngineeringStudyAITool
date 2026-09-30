"""Bounded deterministic regression tools for engineering workflows."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any, Mapping


MAX_DATASET_LENGTH = 10_000
MAX_ABSOLUTE_VALUE = 1e100


class RegressionError(ValueError):
    """Raised when regression inputs or calculations are invalid."""


def _validate_finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RegressionError(f"{name} must be a finite number.")

    result = float(value)

    if not math.isfinite(result):
        raise RegressionError(f"{name} must be finite.")

    if abs(result) > MAX_ABSOLUTE_VALUE:
        raise RegressionError(f"{name} is too large.")

    return result


def _prepare_data(
    x_values: Sequence[float],
    y_values: Sequence[float],
) -> tuple[list[float], list[float]]:
    if isinstance(x_values, (str, bytes)) or not isinstance(
        x_values, Sequence
    ):
        raise RegressionError("x_values must be a numeric sequence.")

    if isinstance(y_values, (str, bytes)) or not isinstance(
        y_values, Sequence
    ):
        raise RegressionError("y_values must be a numeric sequence.")

    if len(x_values) != len(y_values):
        raise RegressionError(
            "x_values and y_values must have the same length."
        )

    if len(x_values) < 2:
        raise RegressionError(
            "Regression requires at least two data points."
        )

    if len(x_values) > MAX_DATASET_LENGTH:
        raise RegressionError(
            f"Regression dataset cannot exceed {MAX_DATASET_LENGTH} points."
        )

    x_data = [
        _validate_finite(value, f"x_values[{index}]")
        for index, value in enumerate(x_values)
    ]
    y_data = [
        _validate_finite(value, f"y_values[{index}]")
        for index, value in enumerate(y_values)
    ]

    return x_data, y_data


def _linear_model(
    x_data: list[float],
    y_data: list[float],
) -> tuple[float, float, float, list[float], list[float]]:
    count = len(x_data)

    mean_x = math.fsum(x_data) / count
    mean_y = math.fsum(y_data) / count

    centered_x = [value - mean_x for value in x_data]
    centered_y = [value - mean_y for value in y_data]

    denominator = math.fsum(value * value for value in centered_x)

    if denominator == 0.0:
        raise RegressionError(
            "Linear regression requires nonzero variance in x_values."
        )

    numerator = math.fsum(
        x_delta * y_delta
        for x_delta, y_delta in zip(centered_x, centered_y)
    )

    slope = numerator / denominator
    intercept = mean_y - slope * mean_x

    fitted_values = [
        intercept + slope * x_value
        for x_value in x_data
    ]

    residuals = [
        y_value - fitted
        for y_value, fitted in zip(y_data, fitted_values)
    ]

    total_sum_squares = math.fsum(
        value * value for value in centered_y
    )

    residual_sum_squares = math.fsum(
        value * value for value in residuals
    )

    if total_sum_squares == 0.0:
        r_squared = 1.0
    else:
        r_squared = 1.0 - (
            residual_sum_squares / total_sum_squares
        )

    values = [
        slope,
        intercept,
        r_squared,
        *fitted_values,
        *residuals,
    ]

    if not all(math.isfinite(value) for value in values):
        raise RegressionError(
            "Regression result exceeded supported numerical limits."
        )

    return (
        slope,
        intercept,
        r_squared,
        fitted_values,
        residuals,
    )


def _correlation(
    x_data: list[float],
    y_data: list[float],
) -> float:
    count = len(x_data)

    mean_x = math.fsum(x_data) / count
    mean_y = math.fsum(y_data) / count

    centered_x = [value - mean_x for value in x_data]
    centered_y = [value - mean_y for value in y_data]

    sum_xx = math.fsum(value * value for value in centered_x)
    sum_yy = math.fsum(value * value for value in centered_y)

    if sum_xx == 0.0 or sum_yy == 0.0:
        raise RegressionError(
            "Correlation requires nonzero variance in both datasets."
        )

    sum_xy = math.fsum(
        x_delta * y_delta
        for x_delta, y_delta in zip(centered_x, centered_y)
    )

    result = sum_xy / math.sqrt(sum_xx * sum_yy)

    if not math.isfinite(result):
        raise RegressionError(
            "Correlation result exceeded supported numerical limits."
        )

    return result


def regression(
    operation: str,
    *,
    x_values: Sequence[float],
    y_values: Sequence[float],
    x: float | None = None,
) -> Mapping[str, Any]:
    """Execute a bounded deterministic regression calculation."""

    if not isinstance(operation, str) or not operation.strip():
        raise RegressionError("operation must be a non-empty string.")

    operation = operation.strip().lower()

    x_data, y_data = _prepare_data(x_values, y_values)

    if operation == "linear":
        slope, intercept, r_squared, fitted_values, residuals = (
            _linear_model(x_data, y_data)
        )

        return {
            "operation": "linear",
            "slope": slope,
            "intercept": intercept,
            "r_squared": r_squared,
            "fitted_values": fitted_values,
            "residuals": residuals,
        }

    if operation == "correlation":
        return {
            "operation": "correlation",
            "correlation": _correlation(x_data, y_data),
        }

    if operation == "predict":
        if x is None:
            raise RegressionError(
                "x is required for prediction."
            )

        target_x = _validate_finite(x, "x")

        slope, intercept, r_squared, _, _ = _linear_model(
            x_data,
            y_data,
        )

        prediction = intercept + slope * target_x

        if not math.isfinite(prediction):
            raise RegressionError(
                "Regression prediction exceeded supported numerical limits."
            )

        return {
            "operation": "predict",
            "prediction": prediction,
            "slope": slope,
            "intercept": intercept,
            "r_squared": r_squared,
        }

    raise RegressionError(
        f"Unsupported regression operation: {operation}"
    )


def regression_handler(
    context,
    arguments,
) -> Mapping[str, Any]:
    if context.is_cancelled():
        context.raise_if_cancelled()

    operation = arguments.get("operation")

    calculation_arguments = {
        key: value
        for key, value in arguments.items()
        if key != "operation"
    }

    result = regression(
        operation,
        **calculation_arguments,
    )

    if context.is_cancelled():
        context.raise_if_cancelled()

    return result
