from __future__ import annotations

import math
from typing import Any, Mapping


MAX_ABSOLUTE_VALUE = 1e100
MAX_BINOMIAL_N = 100_000


class ProbabilityError(ValueError):
    """Raised when a probability calculation is invalid."""


def _validate_probability(p: float) -> float:
    if isinstance(p, bool) or not isinstance(p, (int, float)):
        raise ProbabilityError("p must be a finite number.")

    value = float(p)

    if not math.isfinite(value):
        raise ProbabilityError("p must be finite.")

    if not 0.0 <= value <= 1.0:
        raise ProbabilityError("p must be between 0 and 1.")

    return value


def _validate_finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProbabilityError(f"{name} must be a finite number.")

    result = float(value)

    if not math.isfinite(result):
        raise ProbabilityError(f"{name} must be finite.")

    if abs(result) > MAX_ABSOLUTE_VALUE:
        raise ProbabilityError(f"{name} is too large.")

    return result


def _validate_positive(value: float, name: str) -> float:
    result = _validate_finite(value, name)

    if result <= 0.0:
        raise ProbabilityError(f"{name} must be greater than zero.")

    return result


def _validate_nonnegative_integer(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProbabilityError(f"{name} must be a non-negative integer.")

    if value < 0:
        raise ProbabilityError(f"{name} must be a non-negative integer.")

    return value


def binomial_probability(n: int, k: int, p: float) -> float:
    n = _validate_nonnegative_integer(n, "n")
    k = _validate_nonnegative_integer(k, "k")
    p = _validate_probability(p)

    if k > n:
        raise ProbabilityError("k cannot be greater than n.")
    if n > MAX_BINOMIAL_N:
        raise ProbabilityError("n is too large for binomial probability.")

    result = math.comb(n, k) * (p ** k) * ((1.0 - p) ** (n - k))

    if not math.isfinite(result):
        raise ProbabilityError("Result is not finite.")

    return float(result)


def normal_pdf(
    x: float,
    mean: float = 0.0,
    stddev: float = 1.0,
) -> float:
    x = _validate_finite(x, "x")
    mean = _validate_finite(mean, "mean")
    stddev = _validate_positive(stddev, "stddev")

    z = (x - mean) / stddev

    result = math.exp(-0.5 * z * z) / (
        stddev * math.sqrt(2.0 * math.pi)
    )

    if not math.isfinite(result):
        raise ProbabilityError("Result is not finite.")

    return float(result)


def normal_cdf(
    x: float,
    mean: float = 0.0,
    stddev: float = 1.0,
) -> float:
    x = _validate_finite(x, "x")
    mean = _validate_finite(mean, "mean")
    stddev = _validate_positive(stddev, "stddev")

    z = (x - mean) / (stddev * math.sqrt(2.0))

    result = 0.5 * (1.0 + math.erf(z))

    if not math.isfinite(result):
        raise ProbabilityError("Result is not finite.")

    return float(result)


def probability(
    operation: str,
    **arguments: Any,
) -> Mapping[str, Any]:
    if not isinstance(operation, str) or not operation.strip():
        raise ProbabilityError("operation must be a non-empty string.")

    operation = operation.strip().lower()

    if operation == "binomial":
        result = binomial_probability(
            arguments["n"],
            arguments["k"],
            arguments["p"],
        )
    elif operation == "normal_pdf":
        result = normal_pdf(
            arguments["x"],
            arguments.get("mean", 0.0),
            arguments.get("stddev", 1.0),
        )
    elif operation == "normal_cdf":
        result = normal_cdf(
            arguments["x"],
            arguments.get("mean", 0.0),
            arguments.get("stddev", 1.0),
        )
    else:
        raise ProbabilityError(
            f"Unsupported probability operation: {operation}"
        )

    return {
        "operation": operation,
        "result": result,
    }


def probability_handler(
    context: Any,
    arguments: Mapping[str, Any],
) -> Mapping[str, Any]:
    if context.is_cancelled():
        context.raise_if_cancelled()

    operation = arguments.get("operation")

    calculation_arguments = {
        key: value
        for key, value in arguments.items()
        if key != "operation"
    }

    result = probability(operation, **calculation_arguments)

    if context.is_cancelled():
        context.raise_if_cancelled()

    return result
