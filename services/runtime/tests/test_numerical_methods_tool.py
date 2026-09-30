from __future__ import annotations

import math

import pytest

from anne_runtime.numerical_methods_tool import (
    NumericalMethodsError,
    numerical_methods,
)


def test_bisection_finds_square_root_of_two():
    result = numerical_methods(
        "bisection",
        expression="x**2 - 2",
        lower=1.0,
        upper=2.0,
        tolerance=1e-10,
        max_iterations=100,
    )

    assert result["operation"] == "bisection"
    assert result["root"] == pytest.approx(math.sqrt(2), rel=1e-9)
    assert result["converged"] is True


def test_brent_finds_square_root_of_two():
    result = numerical_methods(
        "brent",
        expression="x**2 - 2",
        lower=1.0,
        upper=2.0,
        tolerance=1e-10,
        max_iterations=100,
    )

    assert result["root"] == pytest.approx(math.sqrt(2), rel=1e-9)
    assert result["converged"] is True


def test_newton_finds_square_root_of_two():
    result = numerical_methods(
        "newton",
        expression="x**2 - 2",
        initial_guess=1.5,
        tolerance=1e-10,
        max_iterations=50,
    )

    assert result["root"] == pytest.approx(math.sqrt(2), rel=1e-9)
    assert result["converged"] is True


def test_secant_finds_square_root_of_two():
    result = numerical_methods(
        "secant",
        expression="x**2 - 2",
        initial_guess=1.0,
        second_guess=2.0,
        tolerance=1e-10,
        max_iterations=50,
    )

    assert result["root"] == pytest.approx(math.sqrt(2), rel=1e-9)
    assert result["converged"] is True


def test_bisection_rejects_interval_without_sign_change():
    with pytest.raises(NumericalMethodsError, match="sign change"):
        numerical_methods(
            "bisection",
            expression="x**2 + 1",
            lower=-1.0,
            upper=1.0,
            tolerance=1e-8,
            max_iterations=50,
        )


def test_newton_rejects_zero_derivative():
    with pytest.raises(NumericalMethodsError, match="derivative"):
        numerical_methods(
            "newton",
            expression="x**3 + 1",
            initial_guess=0.0,
            tolerance=1e-8,
            max_iterations=20,
        )


def test_trapezoidal_integrates_x_squared():
    result = numerical_methods(
        "trapezoidal",
        expression="x**2",
        lower=0.0,
        upper=1.0,
        steps=1000,
    )

    assert result["result"] == pytest.approx(1.0 / 3.0, rel=1e-5)


def test_simpson_integrates_x_squared():
    result = numerical_methods(
        "simpson",
        expression="x**2",
        lower=0.0,
        upper=1.0,
        steps=100,
    )

    assert result["result"] == pytest.approx(1.0 / 3.0, rel=1e-10)


def test_simpson_requires_even_number_of_steps():
    with pytest.raises(NumericalMethodsError, match="even"):
        numerical_methods(
            "simpson",
            expression="x**2",
            lower=0.0,
            upper=1.0,
            steps=99,
        )


def test_central_difference_approximates_derivative():
    result = numerical_methods(
        "central_difference",
        expression="x**2",
        x=2.0,
        step_size=1e-5,
    )

    assert result["result"] == pytest.approx(4.0, rel=1e-5)


def test_forward_difference_approximates_derivative():
    result = numerical_methods(
        "forward_difference",
        expression="x**2",
        x=2.0,
        step_size=1e-5,
    )

    assert result["result"] == pytest.approx(4.0, rel=1e-4)


def test_backward_difference_approximates_derivative():
    result = numerical_methods(
        "backward_difference",
        expression="x**2",
        x=2.0,
        step_size=1e-5,
    )

    assert result["result"] == pytest.approx(4.0, rel=1e-4)


def test_rejects_unknown_operation():
    with pytest.raises(NumericalMethodsError, match="Unsupported"):
        numerical_methods("explode")


def test_rejects_unsafe_expression():
    with pytest.raises(NumericalMethodsError):
        numerical_methods(
            "bisection",
            expression="__import__('os').system('whoami')",
            lower=0.0,
            upper=1.0,
            tolerance=1e-8,
            max_iterations=50,
        )


def test_rejects_excessive_iterations():
    with pytest.raises(NumericalMethodsError, match="iterations"):
        numerical_methods(
            "bisection",
            expression="x - 0.5",
            lower=0.0,
            upper=1.0,
            tolerance=1e-8,
            max_iterations=1_000_001,
        )


def test_rejects_excessive_integration_steps():
    with pytest.raises(NumericalMethodsError, match="steps"):
        numerical_methods(
            "trapezoidal",
            expression="x",
            lower=0.0,
            upper=1.0,
            steps=1_000_001,
        )


def test_rejects_nonpositive_derivative_step():
    with pytest.raises(NumericalMethodsError, match="step"):
        numerical_methods(
            "central_difference",
            expression="x**2",
            x=2.0,
            step_size=0.0,
        )
