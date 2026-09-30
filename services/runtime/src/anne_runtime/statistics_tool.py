from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from typing import Any, Mapping

from .tool_contracts import ToolExecutionError


MAX_DATASET_LENGTH = 10_000
MAX_ABSOLUTE_VALUE = 1e100


class StatisticsError(ToolExecutionError):
    """Raised when statistical inputs or operations are invalid."""


def _validate_values(values: Any) -> tuple[float, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise StatisticsError("values must be a numeric sequence.")

    if not values:
        raise StatisticsError("values must not be empty.")

    if len(values) > MAX_DATASET_LENGTH:
        raise StatisticsError(
            "values exceeds the maximum allowed dataset size."
        )

    validated: list[float] = []

    for index, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise StatisticsError(
                f"values[{index}] must be numeric."
            )

        numeric_value = float(value)

        if not math.isfinite(numeric_value):
            raise StatisticsError(
                f"values[{index}] must be finite."
            )

        if abs(numeric_value) > MAX_ABSOLUTE_VALUE:
            raise StatisticsError(
                f"values[{index}] exceeds the maximum allowed magnitude."
            )

        validated.append(numeric_value)

    return tuple(validated)


def _validate_result(value: float, name: str = "result") -> float:
    value = float(value)

    if not math.isfinite(value):
        raise StatisticsError(f"{name} must be finite.")

    if abs(value) > MAX_ABSOLUTE_VALUE:
        raise StatisticsError(
            f"{name} exceeds the maximum allowed magnitude."
        )

    return value


def statistics_sum(values: Any) -> float:
    data = _validate_values(values)
    return _validate_result(math.fsum(data), "sum")


def statistics_mean(values: Any) -> float:
    data = _validate_values(values)
    return _validate_result(math.fsum(data) / len(data), "mean")


def statistics_median(values: Any) -> float:
    data = sorted(_validate_values(values))
    count = len(data)
    middle = count // 2

    if count % 2:
        return data[middle]

    return _validate_result(
        (data[middle - 1] + data[middle]) / 2,
        "median",
    )


def statistics_mode(values: Any) -> float:
    data = _validate_values(values)
    counts = Counter(data)

    highest_count = max(counts.values())

    if highest_count <= 1:
        raise StatisticsError("values has no mode.")

    modes = [
        value
        for value, count in counts.items()
        if count == highest_count
    ]

    if len(modes) != 1:
        raise StatisticsError(
            "values does not have a unique mode."
        )

    return modes[0]


def statistics_variance(
    values: Any,
    *,
    sample: bool = False,
) -> float:
    data = _validate_values(values)

    if sample and len(data) < 2:
        raise StatisticsError(
            "sample variance requires at least two values."
        )

    mean = math.fsum(data) / len(data)
    denominator = len(data) - 1 if sample else len(data)

    variance = math.fsum(
        (value - mean) ** 2
        for value in data
    ) / denominator

    return _validate_result(variance, "variance")


def statistics_standard_deviation(
    values: Any,
    *,
    sample: bool = False,
) -> float:
    variance = statistics_variance(
        values,
        sample=sample,
    )

    return _validate_result(
        math.sqrt(variance),
        "standard deviation",
    )


def statistics_minimum(values: Any) -> float:
    return min(_validate_values(values))


def statistics_maximum(values: Any) -> float:
    return max(_validate_values(values))


def statistics_range(values: Any) -> float:
    data = _validate_values(values)

    return _validate_result(
        max(data) - min(data),
        "range",
    )


def statistics_percentile(
    values: Any,
    percentile: Any,
) -> float:
    data = sorted(_validate_values(values))

    if isinstance(percentile, bool) or not isinstance(
        percentile,
        (int, float),
    ):
        raise StatisticsError("percentile must be numeric.")

    percentile = float(percentile)

    if not math.isfinite(percentile):
        raise StatisticsError("percentile must be finite.")

    if not 0 <= percentile <= 100:
        raise StatisticsError(
            "percentile must be between 0 and 100."
        )

    if len(data) == 1:
        return data[0]

    position = (len(data) - 1) * percentile / 100
    lower_index = math.floor(position)
    upper_index = math.ceil(position)

    if lower_index == upper_index:
        return data[lower_index]

    fraction = position - lower_index

    return _validate_result(
        data[lower_index]
        + fraction * (data[upper_index] - data[lower_index]),
        "percentile",
    )


def statistics_rms(values: Any) -> float:
    data = _validate_values(values)

    mean_square = math.fsum(
        value * value
        for value in data
    ) / len(data)

    return _validate_result(
        math.sqrt(mean_square),
        "rms",
    )


def statistics(
    operation: str,
    *,
    values: Any,
    sample: bool = False,
    percentile: Any = None,
) -> dict[str, Any]:
    if not isinstance(operation, str) or not operation.strip():
        raise StatisticsError(
            "operation must be a non-empty string."
        )

    operation_name = operation.strip().lower()

    if operation_name == "sum":
        result = statistics_sum(values)
    elif operation_name == "mean":
        result = statistics_mean(values)
    elif operation_name == "median":
        result = statistics_median(values)
    elif operation_name == "mode":
        result = statistics_mode(values)
    elif operation_name == "variance":
        result = statistics_variance(
            values,
            sample=sample,
        )
    elif operation_name in {
        "standard_deviation",
        "stddev",
        "std",
    }:
        result = statistics_standard_deviation(
            values,
            sample=sample,
        )
    elif operation_name in {"min", "minimum"}:
        result = statistics_minimum(values)
    elif operation_name in {"max", "maximum"}:
        result = statistics_maximum(values)
    elif operation_name == "range":
        result = statistics_range(values)
    elif operation_name in {"percentile", "percent"}:
        result = statistics_percentile(
            values,
            percentile,
        )
    elif operation_name == "rms":
        result = statistics_rms(values)
    else:
        raise StatisticsError(
            f"Unsupported statistics operation: {operation_name}"
        )

    return {
        "operation": operation_name,
        "result": result,
    }


def statistics_handler(
    context: Any,
    arguments: Mapping[str, Any],
) -> Mapping[str, Any]:
    if context.is_cancelled():
        raise StatisticsError(
            "Statistics operation was cancelled."
        )

    result = statistics(
        arguments["operation"],
        values=arguments["values"],
        sample=arguments.get("sample", False),
        percentile=arguments.get("percentile"),
    )

    if context.is_cancelled():
        raise StatisticsError(
            "Statistics operation was cancelled."
        )

    return result
