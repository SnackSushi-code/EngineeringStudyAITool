from __future__ import annotations

import math
from typing import Any


MAX_SIGNAL_LENGTH = 100_000
MAX_KERNEL_LENGTH = 10_000
MAX_ABSOLUTE_VALUE = 1e100


class SignalProcessingError(ValueError):
    """Raised when signal-processing arguments are invalid."""


def _validate_values(
    values: Any,
    name: str = "values",
    max_length: int = MAX_SIGNAL_LENGTH,
) -> list[float]:
    if not isinstance(values, (list, tuple)):
        raise SignalProcessingError(f"{name} must be a list or tuple")

    if not values:
        raise SignalProcessingError(f"{name} must not be empty")

    if len(values) > max_length:
        raise SignalProcessingError(
            f"{name} exceeds maximum length of {max_length}"
        )

    result: list[float] = []

    for value in values:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise SignalProcessingError(
                f"{name} values must be numeric"
            ) from exc

        if not math.isfinite(numeric_value):
            raise SignalProcessingError(
                f"{name} values must be finite"
            )

        if abs(numeric_value) > MAX_ABSOLUTE_VALUE:
            raise SignalProcessingError(
                f"{name} values are too large"
            )

        result.append(numeric_value)

    return result


def _validate_window(window: Any, signal_length: int) -> int:
    if isinstance(window, bool):
        raise SignalProcessingError("window must be a positive integer")

    try:
        numeric_window = int(window)
    except (TypeError, ValueError) as exc:
        raise SignalProcessingError(
            "window must be a positive integer"
        ) from exc

    if numeric_window <= 0:
        raise SignalProcessingError(
            "window must be a positive integer"
        )

    if numeric_window > signal_length:
        raise SignalProcessingError(
            "window cannot be larger than the signal"
        )

    return numeric_window


def _moving_average(values: list[float], window: int) -> list[float]:
    running_sum = sum(values[:window])
    result = [running_sum / window]

    for index in range(window, len(values)):
        running_sum += values[index]
        running_sum -= values[index - window]
        result.append(running_sum / window)

    return result


def _rms(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values) / len(values))


def _peak(values: list[float]) -> tuple[float, float]:
    peak_value = max(values, key=abs)
    return peak_value, abs(peak_value)


def _peak_to_peak(values: list[float]) -> float:
    return max(values) - min(values)


def _difference(values: list[float]) -> list[float]:
    return [
        values[index + 1] - values[index]
        for index in range(len(values) - 1)
    ]


def _convolution(
    values: list[float],
    kernel: list[float],
) -> list[float]:
    result_length = len(values) + len(kernel) - 1
    result = [0.0] * result_length

    for index, value in enumerate(values):
        for kernel_index, kernel_value in enumerate(kernel):
            result[index + kernel_index] += value * kernel_value

    return result


def signal_processing(
    operation: str,
    *,
    values: Any,
    window: Any = None,
    kernel: Any = None,
) -> dict[str, Any]:
    """Perform deterministic engineering signal-processing operations."""

    operation_name = str(operation).strip().lower()

    if operation_name not in {
        "moving_average",
        "rms",
        "peak",
        "peak_to_peak",
        "difference",
        "convolution",
    }:
        raise SignalProcessingError(
            f"Unsupported signal-processing operation: {operation_name}"
        )

    signal_values = _validate_values(values)

    if operation_name == "moving_average":
        window_size = _validate_window(window, len(signal_values))
        return {
            "operation": operation_name,
            "values": _moving_average(signal_values, window_size),
            "window": window_size,
        }

    if operation_name == "rms":
        return {
            "operation": operation_name,
            "result": _rms(signal_values),
        }

    if operation_name == "peak":
        peak_value, absolute_peak = _peak(signal_values)
        return {
            "operation": operation_name,
            "result": peak_value,
            "absolute_peak": absolute_peak,
        }

    if operation_name == "peak_to_peak":
        return {
            "operation": operation_name,
            "result": _peak_to_peak(signal_values),
        }

    if operation_name == "difference":
        return {
            "operation": operation_name,
            "values": _difference(signal_values),
        }

    if kernel is None:
        raise SignalProcessingError("kernel must not be empty")

    kernel_values = _validate_values(
        kernel,
        "kernel",
        MAX_KERNEL_LENGTH,
    )

    return {
        "operation": operation_name,
        "values": _convolution(signal_values, kernel_values),
    }


def signal_processing_handler(
    context: Any,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Runtime tool handler for signal processing."""

    if hasattr(context, "raise_if_cancelled"):
        context.raise_if_cancelled()

    operation = str(arguments.get("operation", ""))

    operation_arguments = {
        key: value
        for key, value in arguments.items()
        if key != "operation"
    }

    result = signal_processing(
        operation,
        **operation_arguments,
    )

    if hasattr(context, "raise_if_cancelled"):
        context.raise_if_cancelled()

    return result
