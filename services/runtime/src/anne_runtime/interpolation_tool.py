"""Engineering interpolation methods.

Provides bounded numerical interpolation for engineering/scientific data.
"""

from __future__ import annotations

import math
from typing import Sequence


MAX_DATASET_LENGTH = 10_000
MAX_ABSOLUTE_VALUE = 1e100


class InterpolationError(ValueError):
    """Raised when interpolation input or execution is invalid."""


def _validate_finite(value: float, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise InterpolationError(
            f"{name} must be a finite number."
        ) from exc

    if not math.isfinite(result):
        raise InterpolationError(
            f"{name} must be finite."
        )

    if abs(result) > MAX_ABSOLUTE_VALUE:
        raise InterpolationError(
            f"{name} exceeds the maximum supported magnitude."
        )

    return result


def _prepare_data(
    x_values: Sequence[float],
    y_values: Sequence[float],
    x: float,
    *,
    minimum_points: int,
) -> tuple[list[float], list[float], float]:
    if not isinstance(x_values, Sequence) or isinstance(
        x_values, (str, bytes)
    ):
        raise InterpolationError("x_values must be a sequence.")

    if not isinstance(y_values, Sequence) or isinstance(
        y_values, (str, bytes)
    ):
        raise InterpolationError("y_values must be a sequence.")

    if len(x_values) != len(y_values):
        raise InterpolationError(
            "x_values and y_values must have the same length."
        )

    if len(x_values) < minimum_points:
        raise InterpolationError(
            ("Interpolation requires at least four points." if minimum_points == 4 else f"Interpolation requires at least {minimum_points} points.")
        )

    if len(x_values) > MAX_DATASET_LENGTH:
        raise InterpolationError(
            f"Dataset exceeds the maximum supported length of "
            f"{MAX_DATASET_LENGTH}."
        )

    x_data = [_validate_finite(v, "x_values") for v in x_values]
    y_data = [_validate_finite(v, "y_values") for v in y_values]
    target = _validate_finite(x, "x")

    if len(set(x_data)) != len(x_data):
        raise InterpolationError(
            "x_values must contain distinct values."
        )

    if target < min(x_data) or target > max(x_data):
        raise InterpolationError(
            "extrapolation is not supported; x must be within the "
            "interpolation range."
        )

    return x_data, y_data, target


def _linear(
    x_data: list[float],
    y_data: list[float],
    target: float,
) -> float:
    if target == x_data[0]:
        return y_data[0]

    for index in range(len(x_data) - 1):
        x0 = x_data[index]
        x1 = x_data[index + 1]

        if min(x0, x1) <= target <= max(x0, x1):
            y0 = y_data[index]
            y1 = y_data[index + 1]

            if x1 == x0:
                raise InterpolationError(
                    "Interpolation requires distinct x_values."
                )

            fraction = (target - x0) / (x1 - x0)
            return y0 + fraction * (y1 - y0)

    if target == x_data[-1]:
        return y_data[-1]

    raise InterpolationError(
        "Could not locate x within the interpolation range."
    )


def _lagrange(
    x_data: list[float],
    y_data: list[float],
    target: float,
) -> float:
    result = 0.0

    for i, xi in enumerate(x_data):
        term = y_data[i]

        for j, xj in enumerate(x_data):
            if i == j:
                continue

            denominator = xi - xj

            if denominator == 0:
                raise InterpolationError(
                    "x_values must contain distinct values."
                )

            term *= (target - xj) / denominator

            if not math.isfinite(term):
                raise InterpolationError(
                    "Interpolation result exceeded supported "
                    "numerical limits."
                )

        result += term

        if not math.isfinite(result):
            raise InterpolationError(
                "Interpolation result exceeded supported "
                "numerical limits."
            )

    return result


def _newton_divided_difference(
    x_data: list[float],
    y_data: list[float],
    target: float,
) -> float:
    coefficients = list(y_data)
    n = len(x_data)

    for order in range(1, n):
        for index in range(n - 1, order - 1, -1):
            denominator = (
                x_data[index] - x_data[index - order]
            )

            if denominator == 0:
                raise InterpolationError(
                    "x_values must contain distinct values."
                )

            coefficients[index] = (
                coefficients[index] - coefficients[index - 1]
            ) / denominator

    result = coefficients[-1]

    for index in range(n - 2, -1, -1):
        result = (
            result * (target - x_data[index])
            + coefficients[index]
        )

        if not math.isfinite(result):
            raise InterpolationError(
                "Interpolation result exceeded supported "
                "numerical limits."
            )

    return result


def _cubic_spline(
    x_data: list[float],
    y_data: list[float],
    target: float,
) -> float:
    # Natural cubic spline.
    # Sort the data so descending x-values are supported.
    pairs = sorted(zip(x_data, y_data), key=lambda pair: pair[0])
    xs = [pair[0] for pair in pairs]
    ys = [pair[1] for pair in pairs]

    n = len(xs)

    h = [
        xs[index + 1] - xs[index]
        for index in range(n - 1)
    ]

    if any(step <= 0 for step in h):
        raise InterpolationError(
            "x_values must be strictly ordered after sorting."
        )

    alpha = [0.0] * n

    for index in range(1, n - 1):
        alpha[index] = (
            3.0 / h[index]
            * (ys[index + 1] - ys[index])
            - 3.0 / h[index - 1]
            * (ys[index] - ys[index - 1])
        )

    lower = [0.0] * n
    diagonal = [0.0] * n
    upper = [0.0] * n
    rhs = [0.0] * n

    diagonal[0] = 1.0
    rhs[0] = 0.0

    for index in range(1, n - 1):
        lower[index] = h[index - 1]
        diagonal[index] = (
            2.0 * (xs[index + 1] - xs[index - 1])
        )
        upper[index] = h[index]
        rhs[index] = alpha[index]

    diagonal[-1] = 1.0
    rhs[-1] = 0.0

    # Thomas algorithm.
    for index in range(1, n):
        factor = lower[index] / diagonal[index]
        diagonal[index] -= factor * upper[index]
        rhs[index] -= factor * rhs[index - 1]

    c = [0.0] * n
    c[-1] = rhs[-1] / diagonal[-1]

    for index in range(n - 2, -1, -1):
        c[index] = (
            rhs[index] - upper[index] * c[index + 1]
        ) / diagonal[index]

    b = [0.0] * (n - 1)
    d = [0.0] * (n - 1)

    for index in range(n - 1):
        b[index] = (
            (ys[index + 1] - ys[index]) / h[index]
            - h[index] * (2.0 * c[index] + c[index + 1]) / 3.0
        )

        d[index] = (
            c[index + 1] - c[index]
        ) / (3.0 * h[index])

    if target == xs[-1]:
        interval = n - 2
    else:
        interval = 0

        for index in range(n - 1):
            if xs[index] <= target <= xs[index + 1]:
                interval = index
                break

    dx = target - xs[interval]

    result = (
        ys[interval]
        + b[interval] * dx
        + c[interval] * dx**2
        + d[interval] * dx**3
    )

    if not math.isfinite(result):
        raise InterpolationError(
            "Interpolation result exceeded supported numerical limits."
        )

    return result


def interpolation(
    operation: str,
    *,
    x_values: Sequence[float],
    y_values: Sequence[float],
    x: float,
) -> dict[str, float | str]:
    """Execute a bounded engineering interpolation method."""

    if not isinstance(operation, str):
        raise InterpolationError(
            "operation must be a string."
        )

    operation = operation.strip().lower()

    if operation == "linear":
        x_data, y_data, target = _prepare_data(
            x_values,
            y_values,
            x,
            minimum_points=2,
        )
        result = _linear(x_data, y_data, target)

    elif operation == "lagrange":
        x_data, y_data, target = _prepare_data(
            x_values,
            y_values,
            x,
            minimum_points=2,
        )
        result = _lagrange(x_data, y_data, target)

    elif operation in {"newton", "newton_divided_difference"}:
        x_data, y_data, target = _prepare_data(
            x_values,
            y_values,
            x,
            minimum_points=2,
        )
        result = _newton_divided_difference(
            x_data,
            y_data,
            target,
        )

        operation = "newton"

    elif operation in {"cubic_spline", "spline"}:
        x_data, y_data, target = _prepare_data(
            x_values,
            y_values,
            x,
            minimum_points=4,
        )
        result = _cubic_spline(
            x_data,
            y_data,
            target,
        )

        operation = "cubic_spline"

    else:
        raise InterpolationError(
            f"Unsupported interpolation operation: {operation}"
        )

    result = _validate_finite(result, "result")

    return {
        "operation": operation,
        "result": result,
    }


def interpolation_handler(
    context,
    arguments,
):
    if context.is_cancelled():
        context.raise_if_cancelled()

    operation = arguments.get("operation")

    calculation_arguments = {
        key: value
        for key, value in arguments.items()
        if key != "operation"
    }

    result = interpolation(
        operation,
        **calculation_arguments,
    )

    if context.is_cancelled():
        context.raise_if_cancelled()

    return result
