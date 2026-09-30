import math

import pytest

from anne_runtime.interpolation_tool import (
    InterpolationError,
    interpolation,
)


def test_linear_interpolation_between_two_points():
    result = interpolation(
        "linear",
        x_values=[0.0, 10.0],
        y_values=[0.0, 20.0],
        x=2.5,
    )

    assert result["operation"] == "linear"
    assert result["result"] == pytest.approx(5.0)


def test_lagrange_interpolation():
    result = interpolation(
        "lagrange",
        x_values=[0.0, 1.0, 2.0],
        y_values=[1.0, 3.0, 7.0],
        x=1.5,
    )

    assert result["operation"] == "lagrange"
    assert result["result"] == pytest.approx(4.75)


def test_newton_divided_difference_interpolation():
    result = interpolation(
        "newton",
        x_values=[0.0, 1.0, 2.0],
        y_values=[1.0, 3.0, 7.0],
        x=1.5,
    )

    assert result["operation"] == "newton"
    assert result["result"] == pytest.approx(4.75)


def test_cubic_spline_interpolation():
    result = interpolation(
        "cubic_spline",
        x_values=[0.0, 1.0, 2.0, 3.0],
        y_values=[0.0, 1.0, 4.0, 9.0],
        x=1.5,
    )

    assert result["operation"] == "cubic_spline"
    assert result["result"] == pytest.approx(2.2, rel=1e-2)


def test_interpolation_rejects_extrapolation():
    with pytest.raises(InterpolationError, match="extrapolation"):
        interpolation(
            "linear",
            x_values=[0.0, 10.0],
            y_values=[0.0, 20.0],
            x=12.0,
        )


def test_interpolation_rejects_duplicate_x_values():
    with pytest.raises(InterpolationError, match="distinct"):
        interpolation(
            "lagrange",
            x_values=[0.0, 1.0, 1.0],
            y_values=[0.0, 2.0, 3.0],
            x=0.5,
        )


def test_interpolation_rejects_mismatched_lengths():
    with pytest.raises(InterpolationError, match="same length"):
        interpolation(
            "linear",
            x_values=[0.0, 1.0],
            y_values=[0.0],
            x=0.5,
        )


def test_interpolation_rejects_too_few_points_for_spline():
    with pytest.raises(InterpolationError, match="at least four"):
        interpolation(
            "cubic_spline",
            x_values=[0.0, 1.0, 2.0],
            y_values=[0.0, 1.0, 4.0],
            x=1.5,
        )


def test_interpolation_rejects_nonfinite_values():
    with pytest.raises(InterpolationError, match="finite"):
        interpolation(
            "linear",
            x_values=[0.0, math.inf],
            y_values=[0.0, 1.0],
            x=0.5,
        )


def test_interpolation_rejects_unsupported_operation():
    with pytest.raises(InterpolationError, match="Unsupported"):
        interpolation(
            "polynomial_magic",
            x_values=[0.0, 1.0],
            y_values=[0.0, 1.0],
            x=0.5,
        )


def test_interpolation_rejects_excessive_dataset():
    with pytest.raises(InterpolationError, match="maximum"):
        interpolation(
            "linear",
            x_values=list(range(10001)),
            y_values=list(range(10001)),
            x=5000.5,
        )


def test_linear_interpolation_handles_descending_x_values():
    result = interpolation(
        "linear",
        x_values=[10.0, 0.0],
        y_values=[20.0, 0.0],
        x=2.5,
    )

    assert result["result"] == pytest.approx(5.0)
