import math

import pytest

from anne_runtime.signal_processing_tool import (
    SignalProcessingError,
    signal_processing,
)


def test_moving_average_returns_expected_values():
    result = signal_processing(
        "moving_average",
        values=[1, 2, 3, 4, 5],
        window=3,
    )

    assert result["operation"] == "moving_average"
    assert result["values"] == pytest.approx([2.0, 3.0, 4.0])


def test_rms_returns_expected_value():
    result = signal_processing(
        "rms",
        values=[3, 4],
    )

    assert result["operation"] == "rms"
    assert result["result"] == pytest.approx(math.sqrt(12.5))


def test_peak_returns_largest_absolute_magnitude():
    result = signal_processing(
        "peak",
        values=[-2, 5, -7, 3],
    )

    assert result["operation"] == "peak"
    assert result["result"] == pytest.approx(-7.0)
    assert result["absolute_peak"] == pytest.approx(7.0)


def test_peak_to_peak_returns_range():
    result = signal_processing(
        "peak_to_peak",
        values=[-2, 5, -7, 3],
    )

    assert result["operation"] == "peak_to_peak"
    assert result["result"] == pytest.approx(12.0)


def test_difference_returns_first_difference():
    result = signal_processing(
        "difference",
        values=[1, 4, 9, 16],
    )

    assert result["operation"] == "difference"
    assert result["values"] == pytest.approx([3.0, 5.0, 7.0])


def test_convolution_returns_expected_values():
    result = signal_processing(
        "convolution",
        values=[1, 2, 3],
        kernel=[1, 1],
    )

    assert result["operation"] == "convolution"
    assert result["values"] == pytest.approx([1.0, 3.0, 5.0, 3.0])


def test_signal_processing_rejects_unknown_operation():
    with pytest.raises(
        SignalProcessingError,
        match="Unsupported signal-processing operation",
    ):
        signal_processing(
            "fft",
            values=[1, 2, 3],
        )


def test_signal_processing_rejects_empty_values():
    with pytest.raises(
        SignalProcessingError,
        match="values must not be empty",
    ):
        signal_processing(
            "rms",
            values=[],
        )


def test_signal_processing_rejects_nonfinite_values():
    with pytest.raises(
        SignalProcessingError,
        match="must be finite",
    ):
        signal_processing(
            "rms",
            values=[1.0, math.inf],
        )


def test_moving_average_rejects_invalid_window():
    with pytest.raises(
        SignalProcessingError,
        match="window",
    ):
        signal_processing(
            "moving_average",
            values=[1, 2, 3],
            window=0,
        )


def test_moving_average_rejects_window_larger_than_signal():
    with pytest.raises(
        SignalProcessingError,
        match="window",
    ):
        signal_processing(
            "moving_average",
            values=[1, 2, 3],
            window=4,
        )


def test_convolution_rejects_empty_kernel():
    with pytest.raises(
        SignalProcessingError,
        match="kernel must not be empty",
    ):
        signal_processing(
            "convolution",
            values=[1, 2, 3],
            kernel=[],
        )


def test_signal_processing_rejects_excessively_large_values():
    with pytest.raises(
        SignalProcessingError,
        match="too large",
    ):
        signal_processing(
            "rms",
            values=[1e101, 2],
        )

def test_signal_processing_rejects_excessively_large_kernel():
    with pytest.raises(
        SignalProcessingError,
        match="kernel exceeds maximum length of 10000",
    ):
        signal_processing(
            "convolution",
            values=[1.0],
            kernel=[1.0] * 10_001,
        )
