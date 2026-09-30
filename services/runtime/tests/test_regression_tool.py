import math

import pytest

from anne_runtime.regression_tool import RegressionError, regression


def test_linear_regression_returns_expected_line_and_r_squared():
    result = regression(
        "linear",
        x_values=[1, 2, 3, 4],
        y_values=[3, 5, 7, 9],
    )

    assert result["operation"] == "linear"
    assert result["slope"] == pytest.approx(2.0)
    assert result["intercept"] == pytest.approx(1.0)
    assert result["r_squared"] == pytest.approx(1.0)


def test_linear_regression_returns_fitted_values_and_residuals():
    result = regression(
        "linear",
        x_values=[0, 1, 2],
        y_values=[1, 2, 4],
    )

    assert result["fitted_values"] == pytest.approx([0.8333333333333334, 2.3333333333333335, 3.833333333333333])
    assert result["residuals"] == pytest.approx([0.16666666666666663, -0.3333333333333335, 0.16666666666666696])


def test_predict_uses_fitted_linear_model():
    result = regression(
        "predict",
        x_values=[1, 2, 3, 4],
        y_values=[3, 5, 7, 9],
        x=6,
    )

    assert result["operation"] == "predict"
    assert result["prediction"] == pytest.approx(13.0)
    assert result["slope"] == pytest.approx(2.0)
    assert result["intercept"] == pytest.approx(1.0)


def test_correlation_returns_perfect_positive_correlation():
    result = regression(
        "correlation",
        x_values=[1, 2, 3, 4],
        y_values=[3, 5, 7, 9],
    )

    assert result["operation"] == "correlation"
    assert result["correlation"] == pytest.approx(1.0)


def test_correlation_returns_perfect_negative_correlation():
    result = regression(
        "correlation",
        x_values=[1, 2, 3, 4],
        y_values=[9, 7, 5, 3],
    )

    assert result["correlation"] == pytest.approx(-1.0)


def test_regression_rejects_mismatched_dataset_lengths():
    with pytest.raises(RegressionError, match="same length"):
        regression(
            "linear",
            x_values=[1, 2, 3],
            y_values=[1, 2],
        )


def test_regression_rejects_too_few_points():
    with pytest.raises(RegressionError, match="at least two"):
        regression(
            "linear",
            x_values=[1],
            y_values=[2],
        )


def test_regression_rejects_constant_x_values():
    with pytest.raises(RegressionError, match="variance"):
        regression(
            "linear",
            x_values=[2, 2, 2],
            y_values=[1, 2, 3],
        )


def test_regression_rejects_nonfinite_values():
    with pytest.raises(RegressionError, match="finite"):
        regression(
            "linear",
            x_values=[1, math.inf, 3],
            y_values=[1, 2, 3],
        )


def test_regression_rejects_unknown_operation():
    with pytest.raises(RegressionError, match="Unsupported"):
        regression(
            "quadratic",
            x_values=[1, 2, 3],
            y_values=[1, 4, 9],
        )


def test_regression_rejects_nonfinite_prediction_x():
    with pytest.raises(RegressionError, match="finite"):
        regression(
            "predict",
            x_values=[1, 2, 3],
            y_values=[2, 4, 6],
            x=math.inf,
        )


def test_regression_rejects_excessively_large_values():
    with pytest.raises(RegressionError, match="too large"):
        regression(
            "linear",
            x_values=[1e101, 2e101],
            y_values=[1, 2],
        )
