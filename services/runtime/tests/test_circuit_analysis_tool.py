import math

import pytest

from anne_runtime.circuit_analysis_tool import (
    CircuitAnalysisError,
    circuit_analysis,
    circuit_analysis_handler,
)


def test_ohms_law_calculates_current():
    result = circuit_analysis(
        "ohms_law",
        voltage=12.0,
        resistance=4.0,
    )

    assert result["operation"] == "ohms_law"
    assert result["current"] == pytest.approx(3.0)
    assert result["voltage"] == pytest.approx(12.0)
    assert result["resistance"] == pytest.approx(4.0)


def test_ohms_law_calculates_voltage():
    result = circuit_analysis(
        "ohms_law",
        current=2.0,
        resistance=5.0,
    )

    assert result["voltage"] == pytest.approx(10.0)
    assert result["current"] == pytest.approx(2.0)
    assert result["resistance"] == pytest.approx(5.0)


def test_ohms_law_calculates_resistance():
    result = circuit_analysis(
        "ohms_law",
        voltage=10.0,
        current=2.0,
    )

    assert result["resistance"] == pytest.approx(5.0)
    assert result["voltage"] == pytest.approx(10.0)
    assert result["current"] == pytest.approx(2.0)


def test_series_resistance_returns_sum():
    result = circuit_analysis(
        "series_resistance",
        resistances=[10.0, 20.0, 30.0],
    )

    assert result["operation"] == "series_resistance"
    assert result["result"] == pytest.approx(60.0)


def test_parallel_resistance_returns_equivalent():
    result = circuit_analysis(
        "parallel_resistance",
        resistances=[10.0, 20.0],
    )

    assert result["operation"] == "parallel_resistance"
    assert result["result"] == pytest.approx(20.0 / 3.0)


def test_voltage_divider_returns_output_voltage():
    result = circuit_analysis(
        "voltage_divider",
        input_voltage=12.0,
        r1=10.0,
        r2=20.0,
    )

    assert result["operation"] == "voltage_divider"
    assert result["output_voltage"] == pytest.approx(8.0)


def test_current_divider_returns_branch_currents():
    result = circuit_analysis(
        "current_divider",
        total_current=3.0,
        r1=10.0,
        r2=20.0,
    )

    assert result["operation"] == "current_divider"
    assert result["current_r1"] == pytest.approx(2.0)
    assert result["current_r2"] == pytest.approx(1.0)


def test_power_calculates_power_and_missing_electrical_value():
    result = circuit_analysis(
        "power",
        voltage=12.0,
        current=2.0,
    )

    assert result["operation"] == "power"
    assert result["power"] == pytest.approx(24.0)
    assert result["resistance"] == pytest.approx(6.0)


def test_energy_calculates_energy_from_power_and_time():
    result = circuit_analysis(
        "energy",
        power=100.0,
        time_seconds=60.0,
    )

    assert result["operation"] == "energy"
    assert result["energy_joules"] == pytest.approx(6000.0)


def test_rc_time_constant():
    result = circuit_analysis(
        "rc_time_constant",
        resistance_ohms=1000.0,
        capacitance_farads=1e-6,
    )

    assert result["operation"] == "rc_time_constant"
    assert result["time_constant_seconds"] == pytest.approx(0.001)


def test_rl_time_constant():
    result = circuit_analysis(
        "rl_time_constant",
        inductance_henries=0.1,
        resistance_ohms=10.0,
    )

    assert result["operation"] == "rl_time_constant"
    assert result["time_constant_seconds"] == pytest.approx(0.01)


def test_ohms_law_requires_exactly_two_known_values():
    with pytest.raises(
        CircuitAnalysisError,
        match="requires exactly two",
    ):
        circuit_analysis(
            "ohms_law",
            voltage=12.0,
        )


def test_ohms_law_rejects_zero_resistance():
    with pytest.raises(
        CircuitAnalysisError,
        match="resistance",
    ):
        circuit_analysis(
            "ohms_law",
            voltage=12.0,
            resistance=0.0,
        )


def test_parallel_resistance_rejects_zero_resistance():
    with pytest.raises(
        CircuitAnalysisError,
        match="positive",
    ):
        circuit_analysis(
            "parallel_resistance",
            resistances=[10.0, 0.0],
        )


def test_parallel_resistance_rejects_empty_list():
    with pytest.raises(
        CircuitAnalysisError,
        match="must not be empty",
    ):
        circuit_analysis(
            "parallel_resistance",
            resistances=[],
        )


def test_resistance_list_is_bounded():
    with pytest.raises(
        CircuitAnalysisError,
        match="maximum",
    ):
        circuit_analysis(
            "series_resistance",
            resistances=[1.0] * 10_001,
        )


def test_circuit_analysis_rejects_nonfinite_values():
    with pytest.raises(
        CircuitAnalysisError,
        match="finite",
    ):
        circuit_analysis(
            "power",
            voltage=math.inf,
            current=2.0,
        )


def test_circuit_analysis_rejects_excessively_large_values():
    with pytest.raises(
        CircuitAnalysisError,
        match="maximum supported magnitude",
    ):
        circuit_analysis(
            "power",
            voltage=1e101,
            current=2.0,
        )


def test_voltage_divider_rejects_invalid_resistance():
    with pytest.raises(
        CircuitAnalysisError,
        match="positive",
    ):
        circuit_analysis(
            "voltage_divider",
            input_voltage=12.0,
            r1=0.0,
            r2=20.0,
        )


def test_current_divider_rejects_invalid_resistance():
    with pytest.raises(
        CircuitAnalysisError,
        match="positive",
    ):
        circuit_analysis(
            "current_divider",
            total_current=3.0,
            r1=10.0,
            r2=0.0,
        )


def test_energy_rejects_negative_time():
    with pytest.raises(
        CircuitAnalysisError,
        match="time",
    ):
        circuit_analysis(
            "energy",
            power=100.0,
            time_seconds=-1.0,
        )


def test_rc_time_constant_rejects_negative_capacitance():
    with pytest.raises(
        CircuitAnalysisError,
        match="capacitance",
    ):
        circuit_analysis(
            "rc_time_constant",
            resistance_ohms=1000.0,
            capacitance_farads=-1e-6,
        )


def test_rl_time_constant_rejects_zero_resistance():
    with pytest.raises(
        CircuitAnalysisError,
        match="positive",
    ):
        circuit_analysis(
            "rl_time_constant",
            inductance_henries=0.1,
            resistance_ohms=0.0,
        )


def test_unknown_operation_is_rejected():
    with pytest.raises(
        CircuitAnalysisError,
        match="Unsupported circuit-analysis operation",
    ):
        circuit_analysis(
            "magic_circuit",
            voltage=12.0,
            current=2.0,
        )


def test_handler_checks_cancellation():
    class Context:
        def __init__(self):
            self.calls = 0

        def is_cancelled(self):
            self.calls += 1
            return self.calls >= 2

        def raise_if_cancelled(self):
            self.calls += 1
            if self.calls >= 2:
                raise CircuitAnalysisError("cancelled")

    context = Context()

    with pytest.raises(CircuitAnalysisError, match="cancelled"):
        circuit_analysis_handler(
            context,
            {
                "operation": "series_resistance",
                "resistances": [10.0, 20.0, 30.0],
            },
        )
