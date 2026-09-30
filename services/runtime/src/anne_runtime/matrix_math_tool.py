from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any, Mapping

from .tool_contracts import ToolExecutionError


MAX_MATRIX_ROWS = 32
MAX_MATRIX_COLUMNS = 32
MAX_ABSOLUTE_VALUE = 1e100


class MatrixMathError(ToolExecutionError):
    """Raised when a matrix-math operation cannot be completed safely."""


def _validate_scalar(value: Any, name: str = "scalar") -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MatrixMathError(f"{name} must be a finite number.")

    result = float(value)

    if not math.isfinite(result):
        raise MatrixMathError(f"{name} must be a finite number.")

    if abs(result) > MAX_ABSOLUTE_VALUE:
        raise MatrixMathError(
            f"{name} exceeds the maximum supported magnitude."
        )

    return result


def _validate_matrix(value: Any, name: str = "matrix") -> tuple[tuple[float, ...], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise MatrixMathError(f"{name} must be a sequence of rows.")

    if len(value) == 0:
        raise MatrixMathError(f"{name} must not be empty.")

    if len(value) > MAX_MATRIX_ROWS:
        raise MatrixMathError(
            f"{name} exceeds the maximum of {MAX_MATRIX_ROWS} rows."
        )

    rows: list[tuple[float, ...]] = []
    column_count: int | None = None

    for row_index, row in enumerate(value):
        if isinstance(row, (str, bytes)) or not isinstance(row, Sequence):
            raise MatrixMathError(
                f"{name} row {row_index} must be a sequence."
            )

        if len(row) == 0:
            raise MatrixMathError(
                f"{name} row {row_index} must not be empty."
            )

        if len(row) > MAX_MATRIX_COLUMNS:
            raise MatrixMathError(
                f"{name} exceeds the maximum of "
                f"{MAX_MATRIX_COLUMNS} columns."
            )

        if column_count is None:
            column_count = len(row)
        elif len(row) != column_count:
            raise MatrixMathError(
                f"{name} must be rectangular."
            )

        validated_row = tuple(
            _validate_scalar(element, f"{name}[{row_index}][{column_index}]")
            for column_index, element in enumerate(row)
        )
        rows.append(validated_row)

    return tuple(rows)


def _shape(matrix: tuple[tuple[float, ...], ...]) -> tuple[int, int]:
    return len(matrix), len(matrix[0])


def _require_same_shape(
    left: tuple[tuple[float, ...], ...],
    right: tuple[tuple[float, ...], ...],
) -> None:
    if _shape(left) != _shape(right):
        raise MatrixMathError(
            "Matrices must have the same dimensions."
        )


def _validate_result(
    matrix: Sequence[Sequence[float]],
) -> tuple[tuple[float, ...], ...]:
    return _validate_matrix(matrix, "result")


def matrix_add(
    left: Sequence[Sequence[float]],
    right: Sequence[Sequence[float]],
) -> tuple[tuple[float, ...], ...]:
    a = _validate_matrix(left, "left")
    b = _validate_matrix(right, "right")
    _require_same_shape(a, b)

    return _validate_result(
        [
            [a[row][column] + b[row][column] for column in range(len(a[0]))]
            for row in range(len(a))
        ]
    )


def matrix_subtract(
    left: Sequence[Sequence[float]],
    right: Sequence[Sequence[float]],
) -> tuple[tuple[float, ...], ...]:
    a = _validate_matrix(left, "left")
    b = _validate_matrix(right, "right")
    _require_same_shape(a, b)

    return _validate_result(
        [
            [a[row][column] - b[row][column] for column in range(len(a[0]))]
            for row in range(len(a))
        ]
    )


def matrix_scale(
    matrix: Sequence[Sequence[float]],
    scalar: int | float,
) -> tuple[tuple[float, ...], ...]:
    values = _validate_matrix(matrix)
    factor = _validate_scalar(scalar)

    return _validate_result(
        [
            [value * factor for value in row]
            for row in values
        ]
    )


def matrix_multiply(
    left: Sequence[Sequence[float]],
    right: Sequence[Sequence[float]],
) -> tuple[tuple[float, ...], ...]:
    a = _validate_matrix(left, "left")
    b = _validate_matrix(right, "right")

    a_rows, a_columns = _shape(a)
    b_rows, b_columns = _shape(b)

    if a_columns != b_rows:
        raise MatrixMathError(
            "Matrix dimensions are incompatible for multiplication."
        )

    result = [
        [
            sum(a[row][index] * b[index][column] for index in range(a_columns))
            for column in range(b_columns)
        ]
        for row in range(a_rows)
    ]

    return _validate_result(result)


def matrix_vector_multiply(
    matrix: Sequence[Sequence[float]],
    vector: Sequence[float],
) -> tuple[float, ...]:
    values = _validate_matrix(matrix)
    vector_values = tuple(
        _validate_scalar(value, f"vector[{index}]")
        for index, value in enumerate(vector)
    )

    rows, columns = _shape(values)

    if len(vector_values) != columns:
        raise MatrixMathError(
            "Vector dimension must match the matrix column count."
        )

    result = tuple(
        sum(values[row][column] * vector_values[column] for column in range(columns))
        for row in range(rows)
    )

    for index, value in enumerate(result):
        _validate_scalar(value, f"result[{index}]")

    return result


def matrix_transpose(
    matrix: Sequence[Sequence[float]],
) -> tuple[tuple[float, ...], ...]:
    values = _validate_matrix(matrix)
    rows, columns = _shape(values)

    return _validate_result(
        [
            [values[row][column] for row in range(rows)]
            for column in range(columns)
        ]
    )


def matrix_identity(size: int) -> tuple[tuple[float, ...], ...]:
    if isinstance(size, bool) or not isinstance(size, int):
        raise MatrixMathError("Identity matrix size must be an integer.")

    if size <= 0:
        raise MatrixMathError("Identity matrix size must be positive.")

    if size > MAX_MATRIX_ROWS or size > MAX_MATRIX_COLUMNS:
        raise MatrixMathError(
            f"Identity matrix size cannot exceed {min(MAX_MATRIX_ROWS, MAX_MATRIX_COLUMNS)}."
        )

    return tuple(
        tuple(1.0 if row == column else 0.0 for column in range(size))
        for row in range(size)
    )


def matrix_determinant(
    matrix: Sequence[Sequence[float]],
) -> float:
    values = _validate_matrix(matrix)
    rows, columns = _shape(values)

    if rows != columns:
        raise MatrixMathError("Determinant requires a square matrix.")

    work = [list(row) for row in values]
    determinant = 1.0

    for pivot in range(rows):
        pivot_row = max(
            range(pivot, rows),
            key=lambda row: abs(work[row][pivot]),
        )

        pivot_value = work[pivot_row][pivot]

        if math.isclose(pivot_value, 0.0, abs_tol=1e-15):
            return 0.0

        if pivot_row != pivot:
            work[pivot], work[pivot_row] = work[pivot_row], work[pivot]
            determinant *= -1.0

        pivot_value = work[pivot][pivot]
        determinant *= pivot_value

        for row in range(pivot + 1, rows):
            factor = work[row][pivot] / pivot_value

            for column in range(pivot + 1, rows):
                work[row][column] -= factor * work[pivot][column]

    return _validate_scalar(determinant, "determinant")


def matrix_inverse(
    matrix: Sequence[Sequence[float]],
) -> tuple[tuple[float, ...], ...]:
    values = _validate_matrix(matrix)
    rows, columns = _shape(values)

    if rows != columns:
        raise MatrixMathError("Inverse requires a square matrix.")

    work = [
        list(row) + [
            1.0 if row_index == column_index else 0.0
            for column_index in range(rows)
        ]
        for row_index, row in enumerate(values)
    ]

    for pivot in range(rows):
        pivot_row = max(
            range(pivot, rows),
            key=lambda row: abs(work[row][pivot]),
        )

        pivot_value = work[pivot_row][pivot]

        if math.isclose(pivot_value, 0.0, abs_tol=1e-15):
            raise MatrixMathError("Matrix is singular and cannot be inverted.")

        if pivot_row != pivot:
            work[pivot], work[pivot_row] = work[pivot_row], work[pivot]

        pivot_value = work[pivot][pivot]

        work[pivot] = [
            value / pivot_value
            for value in work[pivot]
        ]

        for row in range(rows):
            if row == pivot:
                continue

            factor = work[row][pivot]

            if math.isclose(factor, 0.0, abs_tol=1e-15):
                continue

            work[row] = [
                work[row][column] - factor * work[pivot][column]
                for column in range(2 * rows)
            ]

    return _validate_result(
        [row[rows:] for row in work]
    )


def matrix_math(
    operation: str,
    *,
    matrix: Sequence[Sequence[float]] | None = None,
    left: Sequence[Sequence[float]] | None = None,
    right: Sequence[Sequence[float]] | None = None,
    vector: Sequence[float] | None = None,
    scalar: int | float | None = None,
    size: int | None = None,
) -> Mapping[str, Any]:
    if not isinstance(operation, str) or not operation.strip():
        raise MatrixMathError(
            "Matrix-math operation must be a non-empty string."
        )

    operation_name = operation.strip().lower()

    if operation_name == "add":
        if left is None or right is None:
            raise MatrixMathError("add requires left and right matrices.")
        result = matrix_add(left, right)

    elif operation_name == "subtract":
        if left is None or right is None:
            raise MatrixMathError("subtract requires left and right matrices.")
        result = matrix_subtract(left, right)

    elif operation_name in {"scale", "scalar_multiply"}:
        if matrix is None or scalar is None:
            raise MatrixMathError("scale requires matrix and scalar.")
        result = matrix_scale(matrix, scalar)

    elif operation_name == "multiply":
        if left is None or right is None:
            raise MatrixMathError("multiply requires left and right matrices.")
        result = matrix_multiply(left, right)

    elif operation_name in {"matrix_vector_multiply", "vector_multiply"}:
        if matrix is None or vector is None:
            raise MatrixMathError(
                "matrix_vector_multiply requires matrix and vector."
            )
        result = matrix_vector_multiply(matrix, vector)

    elif operation_name == "transpose":
        if matrix is None:
            raise MatrixMathError("transpose requires matrix.")
        result = matrix_transpose(matrix)

    elif operation_name == "determinant":
        if matrix is None:
            raise MatrixMathError("determinant requires matrix.")
        result = matrix_determinant(matrix)

    elif operation_name == "inverse":
        if matrix is None:
            raise MatrixMathError("inverse requires matrix.")
        result = matrix_inverse(matrix)

    elif operation_name == "identity":
        if size is None:
            raise MatrixMathError("identity requires size.")
        result = matrix_identity(size)

    else:
        raise MatrixMathError(
            f"Unsupported matrix operation: {operation_name}"
        )

    return {
        "operation": operation_name,
        "result": result,
    }


def matrix_math_handler(context: Any, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    if context.is_cancelled():
        raise MatrixMathError("Matrix-math operation was cancelled.")

    return matrix_math(
        arguments["operation"],
        matrix=arguments.get("matrix"),
        left=arguments.get("left"),
        right=arguments.get("right"),
        vector=arguments.get("vector"),
        scalar=arguments.get("scalar"),
        size=arguments.get("size"),
    )
