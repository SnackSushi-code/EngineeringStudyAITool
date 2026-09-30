from __future__ import annotations

import pytest

from anne_runtime.matrix_math_tool import (
    MatrixMathError,
    matrix_add,
    matrix_determinant,
    matrix_identity,
    matrix_inverse,
    matrix_math,
    matrix_multiply,
    matrix_scale,
    matrix_subtract,
    matrix_transpose,
    matrix_vector_multiply,
)


# ============================================================
# BASIC OPERATIONS
# ============================================================

def test_add():
    assert matrix_add(
        [[1, 2], [3, 4]],
        [[5, 6], [7, 8]],
    ) == (
        (6.0, 8.0),
        (10.0, 12.0),
    )


def test_subtract():
    assert matrix_subtract(
        [[5, 6], [7, 8]],
        [[1, 2], [3, 4]],
    ) == (
        (4.0, 4.0),
        (4.0, 4.0),
    )


def test_scale():
    assert matrix_scale(
        [[1, 2], [3, 4]],
        2,
    ) == (
        (2.0, 4.0),
        (6.0, 8.0),
    )


def test_multiply():
    assert matrix_multiply(
        [[1, 2], [3, 4]],
        [[5, 6], [7, 8]],
    ) == (
        (19.0, 22.0),
        (43.0, 50.0),
    )


def test_matrix_vector_multiply():
    assert matrix_vector_multiply(
        [[1, 2], [3, 4]],
        [5, 6],
    ) == (
        17.0,
        39.0,
    )


def test_transpose():
    assert matrix_transpose(
        [[1, 2, 3], [4, 5, 6]],
    ) == (
        (1.0, 4.0),
        (2.0, 5.0),
        (3.0, 6.0),
    )


def test_identity():
    assert matrix_identity(3) == (
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    )


def test_determinant():
    assert matrix_determinant(
        [[1, 2], [3, 4]],
    ) == pytest.approx(-2.0)


def test_inverse():
    result = matrix_inverse(
        [[4, 7], [2, 6]],
    )

    expected = (
        (0.6, -0.7),
        (-0.2, 0.4),
    )

    for result_row, expected_row in zip(result, expected):
        assert result_row == pytest.approx(expected_row)


def test_dispatcher():
    result = matrix_math(
        "multiply",
        left=[[1, 2], [3, 4]],
        right=[[5, 6], [7, 8]],
    )

    assert result == {
        "operation": "multiply",
        "result": (
            (19.0, 22.0),
            (43.0, 50.0),
        ),
    }


# ============================================================
# REQUIRED ARGUMENT VALIDATION
# ============================================================

@pytest.mark.parametrize(
    "operation",
    [
        "add",
        "subtract",
        "scale",
        "multiply",
        "matrix_vector_multiply",
        "transpose",
        "determinant",
        "inverse",
        "identity",
    ],
)
def test_missing_required_arguments(operation):
    with pytest.raises(MatrixMathError):
        matrix_math(operation)


# ============================================================
# MATRIX SHAPE / DIMENSION VALIDATION
# ============================================================

def test_rejects_non_rectangular_matrix():
    with pytest.raises(MatrixMathError, match="rectangular"):
        matrix_add(
            [[1, 2], [3]],
            [[1, 2], [3, 4]],
        )


def test_rejects_dimension_mismatch_for_addition():
    with pytest.raises(MatrixMathError, match="same dimensions"):
        matrix_add(
            [[1, 2]],
            [[1], [2]],
        )


def test_rejects_dimension_mismatch_for_multiplication():
    with pytest.raises(MatrixMathError, match="incompatible"):
        matrix_multiply(
            [[1, 2]],
            [[1, 2]],
        )


def test_rejects_wrong_vector_dimension():
    with pytest.raises(MatrixMathError, match="column count"):
        matrix_vector_multiply(
            [[1, 2], [3, 4]],
            [1],
        )


# ============================================================
# SQUARE MATRIX VALIDATION
# ============================================================

def test_rejects_non_square_determinant():
    with pytest.raises(MatrixMathError, match="square"):
        matrix_determinant(
            [[1, 2, 3], [4, 5, 6]],
        )


def test_rejects_non_square_inverse():
    with pytest.raises(MatrixMathError, match="square"):
        matrix_inverse(
            [[1, 2, 3], [4, 5, 6]],
        )


def test_rejects_singular_inverse():
    with pytest.raises(MatrixMathError, match="singular"):
        matrix_inverse(
            [[1, 2], [2, 4]],
        )


# ============================================================
# IDENTITY VALIDATION
# ============================================================

def test_rejects_zero_identity_size():
    with pytest.raises(MatrixMathError, match="positive"):
        matrix_identity(0)


def test_rejects_oversized_identity():
    with pytest.raises(MatrixMathError, match="cannot exceed"):
        matrix_identity(33)


# ============================================================
# OPERATION VALIDATION
# ============================================================

def test_rejects_unsupported_operation():
    with pytest.raises(MatrixMathError, match="Unsupported"):
        matrix_math(
            "explode",
            matrix=[[1]],
        )


def test_operation_name_is_normalized():
    result = matrix_math(
        "  MULTIPLY  ",
        left=[[2]],
        right=[[3]],
    )

    assert result["operation"] == "multiply"
    assert result["result"] == ((6.0,),)


def test_rejects_empty_operation():
    with pytest.raises(MatrixMathError, match="non-empty"):
        matrix_math("")


def test_rejects_non_string_operation():
    with pytest.raises(MatrixMathError, match="non-empty"):
        matrix_math(None)


# ============================================================
# VALUE VALIDATION
# ============================================================

def test_rejects_non_numeric_matrix_value():
    with pytest.raises(MatrixMathError):
        matrix_add(
            [[1, "bad"]],
            [[2, 3]],
        )


def test_rejects_non_finite_value():
    with pytest.raises(MatrixMathError):
        matrix_add(
            [[float("inf")]],
            [[1]],
        )


def test_rejects_excessive_matrix_dimensions():
    oversized = [[1.0] * 33]

    with pytest.raises(MatrixMathError, match="maximum"):
        matrix_add(oversized, oversized)


def test_rejects_excessive_numeric_magnitude():
    with pytest.raises(MatrixMathError, match="maximum supported magnitude"):
        matrix_add(
            [[1e101]],
            [[1]],
        )


# ============================================================
# NUMERICAL CORRECTNESS
# ============================================================

def test_inverse_of_identity():
    identity = matrix_identity(3)
    result = matrix_inverse(identity)

    for result_row, expected_row in zip(result, identity):
        assert result_row == pytest.approx(expected_row)


def test_determinant_of_identity():
    assert matrix_determinant(
        matrix_identity(4),
    ) == pytest.approx(1.0)


def test_zero_determinant():
    assert matrix_determinant(
        [[1, 2], [2, 4]],
    ) == pytest.approx(0.0)
