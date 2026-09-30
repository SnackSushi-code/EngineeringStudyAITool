import math

import pytest

from anne_runtime.vector_math_tool import (
    VectorMathError,
    vector_add,
    vector_angle,
    vector_cross,
    vector_dot,
    vector_magnitude,
    vector_math,
    vector_normalize,
    vector_scale,
    vector_subtract,
)


def test_magnitude():
    assert vector_magnitude([3, 4]) == pytest.approx(5.0)


def test_magnitude_three_dimensions():
    assert vector_magnitude([1, 2, 2]) == pytest.approx(3.0)


def test_add():
    assert vector_add([1, 2, 3], [4, 5, 6]) == pytest.approx((5, 7, 9))


def test_subtract():
    assert vector_subtract([5, 7, 9], [2, 3, 4]) == pytest.approx((3, 4, 5))


def test_scale():
    assert vector_scale([1, 2, 3], 2.5) == pytest.approx((2.5, 5.0, 7.5))


def test_dot():
    assert vector_dot([1, 2, 3], [4, 5, 6]) == pytest.approx(32.0)


def test_cross():
    assert vector_cross([1, 0, 0], [0, 1, 0]) == pytest.approx((0, 0, 1))


def test_cross_reverse_direction():
    assert vector_cross([0, 1, 0], [1, 0, 0]) == pytest.approx((0, 0, -1))


def test_normalize():
    assert vector_normalize([3, 4]) == pytest.approx((0.6, 0.8))


def test_angle():
    assert vector_angle([1, 0], [0, 1]) == pytest.approx(math.pi / 2)


def test_angle_same_direction():
    assert vector_angle([1, 2, 3], [2, 4, 6]) == pytest.approx(0.0)


def test_operation_dispatch():
    assert vector_math("magnitude", vector=[3, 4])["result"] == pytest.approx(5.0)
    assert vector_math("dot", left=[1, 2], right=[3, 4])["result"] == pytest.approx(11.0)


def test_operation_is_case_insensitive():
    assert vector_math("DOT", left=[1, 2], right=[3, 4])["result"] == pytest.approx(11.0)


def test_dimension_mismatch_rejected():
    with pytest.raises(VectorMathError, match="dimensions must match"):
        vector_add([1, 2], [3, 4, 5])


def test_cross_requires_three_dimensions():
    with pytest.raises(VectorMathError, match="3-dimensional"):
        vector_cross([1, 2], [3, 4])


def test_zero_vector_normalization_rejected():
    with pytest.raises(VectorMathError, match="Zero vector"):
        vector_normalize([0, 0, 0])


def test_zero_vector_angle_rejected():
    with pytest.raises(VectorMathError, match="zero vector"):
        vector_angle([0, 0], [1, 0])


def test_nonfinite_component_rejected():
    with pytest.raises(VectorMathError, match="finite"):
        vector_magnitude([1, float("inf")])


def test_nan_component_rejected():
    with pytest.raises(VectorMathError, match="finite"):
        vector_magnitude([1, float("nan")])


def test_boolean_component_rejected():
    with pytest.raises(VectorMathError, match="finite"):
        vector_magnitude([1, True])


def test_empty_vector_rejected():
    with pytest.raises(VectorMathError, match="must not be empty"):
        vector_magnitude([])


def test_vector_length_limit_rejected():
    with pytest.raises(VectorMathError, match="maximum vector length"):
        vector_magnitude([1] * 65)


def test_scalar_validation():
    with pytest.raises(VectorMathError, match="scalar"):
        vector_scale([1, 2], float("inf"))


def test_unsupported_operation_rejected():
    with pytest.raises(VectorMathError, match="Unsupported vector operation"):
        vector_math("matrix_inverse", vector=[1, 2])


def test_missing_operation_rejected():
    with pytest.raises(VectorMathError, match="non-empty"):
        vector_math("")


def test_result_values_are_finite():
    result = vector_math("scale", vector=[1, -2, 3], scalar=2)
    assert all(math.isfinite(value) for value in result["result"])
