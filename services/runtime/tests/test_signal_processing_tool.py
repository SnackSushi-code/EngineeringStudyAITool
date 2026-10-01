import math

import pytest

from anne_runtime.signal_processing_tool import (
    _fft,
    SignalProcessingError,
    frequency_domain,
    frequency_domain_handler,
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

def test_dft_returns_expected_impulse_spectrum():
    result = frequency_domain(
        "dft",
        values=[1.0, 0.0, 0.0, 0.0],
    )

    assert result["operation"] == "dft"
    assert result["spectrum"] == [
        {"real": pytest.approx(1.0), "imag": pytest.approx(0.0)},
        {"real": pytest.approx(1.0), "imag": pytest.approx(0.0)},
        {"real": pytest.approx(1.0), "imag": pytest.approx(0.0)},
        {"real": pytest.approx(1.0), "imag": pytest.approx(0.0)},
    ]


def test_fft_returns_expected_impulse_spectrum():
    result = frequency_domain(
        "fft",
        values=[1.0, 0.0, 0.0, 0.0],
    )

    assert result["operation"] == "fft"
    assert result["spectrum"] == [
        {"real": pytest.approx(1.0), "imag": pytest.approx(0.0)},
        {"real": pytest.approx(1.0), "imag": pytest.approx(0.0)},
        {"real": pytest.approx(1.0), "imag": pytest.approx(0.0)},
        {"real": pytest.approx(1.0), "imag": pytest.approx(0.0)},
    ]


def test_fft_matches_dft():
    values = [1.0, 2.0, 3.0, 4.0]

    dft = frequency_domain("dft", values=values)
    fft = frequency_domain("fft", values=values)

    for expected, actual in zip(dft["spectrum"], fft["spectrum"]):
        assert actual["real"] == pytest.approx(expected["real"])
        assert actual["imag"] == pytest.approx(expected["imag"])


def test_magnitude_spectrum_returns_expected_values():
    result = frequency_domain(
        "magnitude_spectrum",
        values=[1.0, 0.0, 0.0, 0.0],
        sample_rate=100.0,
    )

    assert result["operation"] == "magnitude_spectrum"
    assert result["frequencies"] == pytest.approx(
        [0.0, 25.0, 50.0, 75.0]
    )
    assert result["magnitudes"] == pytest.approx(
        [1.0, 1.0, 1.0, 1.0]
    )
    assert result["sample_rate"] == pytest.approx(100.0)


def test_frequency_domain_rejects_non_power_of_two_fft():
    with pytest.raises(
        SignalProcessingError,
        match="power of two",
    ):
        frequency_domain(
            "fft",
            values=[1.0, 2.0, 3.0],
        )


def test_frequency_domain_rejects_invalid_sample_rate():
    with pytest.raises(
        SignalProcessingError,
        match="sample_rate",
    ):
        frequency_domain(
            "magnitude_spectrum",
            values=[1.0, 0.0, 0.0, 0.0],
            sample_rate=0,
        )


def test_frequency_domain_rejects_unknown_operation():
    with pytest.raises(
        SignalProcessingError,
        match="Unsupported frequency-domain operation",
    ):
        frequency_domain(
            "wavelet",
            values=[1.0, 2.0],
        )


def test_frequency_domain_rejects_excessively_large_signal():
    with pytest.raises(
        SignalProcessingError,
        match="maximum length",
    ):
        frequency_domain(
            "fft",
            values=[1.0] * 100_001,
        )


def test_frequency_domain_rejects_nonfinite_sample_rate():
    with pytest.raises(
        SignalProcessingError,
        match="sample_rate",
    ):
        frequency_domain(
            "magnitude_spectrum",
            values=[1.0, 0.0, 0.0, 0.0],
            sample_rate=math.inf,
        )

def test_frequency_domain_dft_rejects_excessive_workload():
    values = [0.0] * 4097

    with pytest.raises(
        SignalProcessingError,
        match="DFT signal length exceeds maximum",
    ):
        frequency_domain(
            "dft",
            values=values,
        )

def test_frequency_domain_handler_honors_cancellation_during_fft():
    class CancelledError(RuntimeError):
        pass

    class Context:
        def __init__(self):
            self.calls = 0

        def raise_if_cancelled(self):
            self.calls += 1
            if self.calls >= 3:
                raise CancelledError("cancelled")

    context = Context()

    with pytest.raises(CancelledError, match="cancelled"):
        frequency_domain_handler(
            context,
            {
                "operation": "fft",
                "values": [float(index) for index in range(1024)],
            },
        )

    assert context.calls >= 3
