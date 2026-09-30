import math

import pytest

from anne_runtime.complex_math_tool import (
    ComplexMathError,
    complex_add,
    complex_subtract,
    complex_multiply,
    complex_divide,
    complex_magnitude,
    complex_phase,
    complex_conjugate,
    complex_real,
    complex_imaginary,
    complex_to_polar,
    polar_to_complex,
    complex_math,
)


def test_adds_complex_numbers():
    assert complex_add(
        {"real": 1, "imaginary": 2},
        {"real": 3, "imaginary": 4},
    ) == {"real": 4.0, "imaginary": 6.0}


def test_subtracts_complex_numbers():
    assert complex_subtract(
        {"real": 5, "imaginary": 7},
        {"real": 2, "imaginary": 3},
    ) == {"real": 3.0, "imaginary": 4.0}


def test_multiplies_complex_numbers():
    assert complex_multiply(
        {"real": 1, "imaginary": 2},
        {"real": 3, "imaginary": 4},
    ) == {"real": -5.0, "imaginary": 10.0}


def test_divides_complex_numbers():
    result = complex_divide(
        {"real": 1, "imaginary": 2},
        {"real": 3, "imaginary": 4},
    )

    assert result["real"] == pytest.approx(0.44)
    assert result["imaginary"] == pytest.approx(0.08)


def test_rejects_division_by_zero():
    with pytest.raises(ComplexMathError, match="zero"):
        complex_divide(
            {"real": 1, "imaginary": 2},
            {"real": 0, "imaginary": 0},
        )


def test_calculates_magnitude():
    assert complex_magnitude(
        {"real": 3, "imaginary": 4},
    ) == pytest.approx(5.0)


def test_calculates_phase():
    assert complex_phase(
        {"real": 1, "imaginary": 1},
    ) == pytest.approx(math.pi / 4)


def test_calculates_conjugate():
    assert complex_conjugate(
        {"real": 3, "imaginary": 4},
    ) == {"real": 3.0, "imaginary": -4.0}


def test_extracts_real_component():
    assert complex_real(
        {"real": 3, "imaginary": 4},
    ) == 3.0


def test_extracts_imaginary_component():
    assert complex_imaginary(
        {"real": 3, "imaginary": 4},
    ) == 4.0


def test_converts_complex_to_polar():
    result = complex_to_polar(
        {"real": 3, "imaginary": 4},
    )

    assert result["magnitude"] == pytest.approx(5.0)
    assert result["phase"] == pytest.approx(math.atan2(4, 3))


def test_converts_polar_to_complex():
    result = polar_to_complex(
        magnitude=5,
        phase=math.atan2(4, 3),
    )

    assert result["real"] == pytest.approx(3.0)
    assert result["imaginary"] == pytest.approx(4.0)


def test_dispatcher_returns_operation_and_result():
    result = complex_math(
        "multiply",
        left={"real": 1, "imaginary": 2},
        right={"real": 3, "imaginary": 4},
    )

    assert result == {
        "operation": "multiply",
        "result": {"real": -5.0, "imaginary": 10.0},
    }


@pytest.mark.parametrize(
    "value",
    [
        {"real": float("nan"), "imaginary": 1},
        {"real": 1, "imaginary": float("inf")},
        {"real": float("-inf"), "imaginary": 1},
    ],
)
def test_rejects_non_finite_components(value):
    with pytest.raises(ComplexMathError):
        complex_magnitude(value)


def test_rejects_malformed_complex_value():
    with pytest.raises(ComplexMathError):
        complex_magnitude({"real": 1})


def test_rejects_boolean_components():
    with pytest.raises(ComplexMathError):
        complex_magnitude({"real": True, "imaginary": 1})


def test_rejects_unsupported_operation():
    with pytest.raises(ComplexMathError, match="Unsupported"):
        complex_math("explode")


def test_rejects_invalid_polar_magnitude():
    with pytest.raises(ComplexMathError):
        polar_to_complex(
            magnitude=-1,
            phase=0,
        )
