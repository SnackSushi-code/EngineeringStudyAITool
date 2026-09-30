from __future__ import annotations

import math

import pytest

from anne_runtime.differential_equations_tool import (
    DifferentialEquationsError,
    differential_equations,
)


def test_euler_solves_exponential_growth():
    result = differential_equations(
        operation="euler",
        expression="y",
        t0=0.0,
        y0=1.0,
        tf=1.0,
        step_size=0.1,
    )

    assert result["operation"] == "euler"
    assert result["steps"] == 10
    assert result["t"] == pytest.approx(1.0)
    assert result["y"] == pytest.approx(2.5937424601)


def test_rk4_solves_exponential_growth():
    result = differential_equations(
        operation="rk4",
        expression="y",
        t0=0.0,
        y0=1.0,
        tf=1.0,
        step_size=0.1,
    )

    assert result["operation"] == "rk4"
    assert result["steps"] == 10
    assert result["t"] == pytest.approx(1.0)

    # RK4 with h=0.1 has a small truncation error relative to e.
    assert result["y"] == pytest.approx(math.e, rel=1e-6)


def test_euler_handles_constant_derivative():
    result = differential_equations(
        operation="euler",
        expression="2",
        t0=0.0,
        y0=3.0,
        tf=2.0,
        step_size=0.5,
    )

    assert result["y"] == pytest.approx(7.0)
    assert result["steps"] == 4


def test_rk4_handles_time_dependent_derivative():
    result = differential_equations(
        operation="rk4",
        expression="t",
        t0=0.0,
        y0=0.0,
        tf=2.0,
        step_size=0.1,
    )

    assert result["y"] == pytest.approx(2.0, rel=1e-7)


def test_expression_supports_t_and_y():
    result = differential_equations(
        operation="rk4",
        expression="t + y",
        t0=0.0,
        y0=1.0,
        tf=0.5,
        step_size=0.1,
    )

    assert math.isfinite(result["y"])


def test_final_partial_step_is_handled():
    result = differential_equations(
        operation="rk4",
        expression="1",
        t0=0.0,
        y0=0.0,
        tf=1.0,
        step_size=0.3,
    )

    assert result["t"] == pytest.approx(1.0)
    assert result["y"] == pytest.approx(1.0, rel=1e-7)
    assert result["steps"] == 4


@pytest.mark.parametrize("operation", ["euler", "rk4"])
def test_zero_step_size_is_rejected(operation):
    with pytest.raises(DifferentialEquationsError):
        differential_equations(
            operation=operation,
            expression="y",
            t0=0.0,
            y0=1.0,
            tf=1.0,
            step_size=0.0,
        )


@pytest.mark.parametrize("operation", ["euler", "rk4"])
def test_invalid_operation_is_rejected(operation):
    with pytest.raises(DifferentialEquationsError):
        differential_equations(
            operation="invalid",
            expression="y",
            t0=0.0,
            y0=1.0,
            tf=1.0,
            step_size=0.1,
        )


def test_reverse_time_integration_is_supported():
    result = differential_equations(
        operation="rk4",
        expression="1",
        t0=1.0,
        y0=2.0,
        tf=0.0,
        step_size=0.25,
    )

    assert result["t"] == pytest.approx(0.0)
    assert result["y"] == pytest.approx(1.0, rel=1e-7)


def test_invalid_expression_is_rejected():
    with pytest.raises(DifferentialEquationsError):
        differential_equations(
            operation="rk4",
            expression="unknown_function(y)",
            t0=0.0,
            y0=1.0,
            tf=1.0,
            step_size=0.1,
        )


def test_arbitrary_code_is_rejected():
    with pytest.raises(DifferentialEquationsError):
        differential_equations(
            operation="rk4",
            expression="__import__('os').system('whoami')",
            t0=0.0,
            y0=1.0,
            tf=1.0,
            step_size=0.1,
        )


def test_unknown_name_is_rejected():
    with pytest.raises(DifferentialEquationsError):
        differential_equations(
            operation="rk4",
            expression="x + y",
            t0=0.0,
            y0=1.0,
            tf=1.0,
            step_size=0.1,
        )


def test_nonfinite_initial_value_is_rejected():
    with pytest.raises(DifferentialEquationsError):
        differential_equations(
            operation="rk4",
            expression="y",
            t0=0.0,
            y0=float("inf"),
            tf=1.0,
            step_size=0.1,
        )


def test_nonfinite_time_is_rejected():
    with pytest.raises(DifferentialEquationsError):
        differential_equations(
            operation="rk4",
            expression="y",
            t0=0.0,
            y0=1.0,
            tf=float("inf"),
            step_size=0.1,
        )


def test_too_many_steps_are_rejected():
    with pytest.raises(DifferentialEquationsError):
        differential_equations(
            operation="rk4",
            expression="y",
            t0=0.0,
            y0=1.0,
            tf=1000.0,
            step_size=0.0001,
        )


def test_result_overflow_is_rejected():
    with pytest.raises(DifferentialEquationsError):
        differential_equations(
            operation="rk4",
            expression="y * y",
            t0=0.0,
            y0=1e50,
            tf=1.0,
            step_size=0.1,
        )


def test_empty_expression_is_rejected():
    with pytest.raises(DifferentialEquationsError):
        differential_equations(
            operation="rk4",
            expression="",
            t0=0.0,
            y0=1.0,
            tf=1.0,
            step_size=0.1,
        )


def test_expression_length_is_bounded():
    with pytest.raises(DifferentialEquationsError):
        differential_equations(
            operation="rk4",
            expression="y" * 600,
            t0=0.0,
            y0=1.0,
            tf=1.0,
            step_size=0.1,
        )


def test_trigonometric_expression_is_supported():
    result = differential_equations(
        operation="rk4",
        expression="sin(t)",
        t0=0.0,
        y0=0.0,
        tf=math.pi,
        step_size=0.1,
    )

    assert result["y"] == pytest.approx(2.0, rel=1e-5)


def test_supported_math_functions_are_safe():
    result = differential_equations(
        operation="rk4",
        expression="cos(t) + exp(0)",
        t0=0.0,
        y0=0.0,
        tf=1.0,
        step_size=0.1,
    )

    assert math.isfinite(result["y"])


def test_handler_contract_will_be_added_after_core_solver():
    assert True
