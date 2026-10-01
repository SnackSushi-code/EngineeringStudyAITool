from __future__ import annotations

import math

import pytest

from anne_runtime.statics_tool import (
    StaticsError,
    statics,
)


def test_force_components():
    result = statics(
        "force_components",
        magnitude=100.0,
        angle_degrees=30.0,
    )

    assert result["operation"] == "force_components"
    assert result["fx"] == pytest.approx(100.0 * math.cos(math.radians(30.0)))
    assert result["fy"] == pytest.approx(50.0)


def test_force_components_zero_angle():
    result = statics(
        "force_components",
        magnitude=100.0,
        angle_degrees=0.0,
    )

    assert result["fx"] == pytest.approx(100.0)
    assert result["fy"] == pytest.approx(0.0)


def test_force_components_negative_angle():
    result = statics(
        "force_components",
        magnitude=100.0,
        angle_degrees=-30.0,
    )

    assert result["fx"] == pytest.approx(86.6025403784)
    assert result["fy"] == pytest.approx(-50.0)


def test_resultant_force():
    result = statics(
        "resultant_force",
        fx=3.0,
        fy=4.0,
    )

    assert result["operation"] == "resultant_force"
    assert result["resultant"] == pytest.approx(5.0)


def test_resultant_force_negative_components():
    result = statics(
        "resultant_force",
        fx=-3.0,
        fy=-4.0,
    )

    assert result["resultant"] == pytest.approx(5.0)


def test_resultant_angle():
    result = statics(
        "resultant_angle",
        fx=3.0,
        fy=4.0,
    )

    assert result["angle_degrees"] == pytest.approx(
        math.degrees(math.atan2(4.0, 3.0))
    )


def test_resultant_angle_negative_quadrant():
    result = statics(
        "resultant_angle",
        fx=-3.0,
        fy=4.0,
    )

    assert result["angle_degrees"] == pytest.approx(
        math.degrees(math.atan2(4.0, -3.0))
    )


def test_moment_2d():
    result = statics(
        "moment_2d",
        x=2.0,
        y=0.0,
        fx=0.0,
        fy=10.0,
    )

    assert result["operation"] == "moment_2d"
    assert result["moment"] == pytest.approx(20.0)


def test_moment_2d_negative_rotation():
    result = statics(
        "moment_2d",
        x=0.0,
        y=2.0,
        fx=10.0,
        fy=0.0,
    )

    assert result["moment"] == pytest.approx(-20.0)


def test_moment_from_force():
    result = statics(
        "moment_from_force",
        force=100.0,
        perpendicular_distance=2.0,
        angle_degrees=90.0,
    )

    assert result["moment"] == pytest.approx(200.0)


def test_moment_from_force_zero_angle():
    result = statics(
        "moment_from_force",
        force=100.0,
        perpendicular_distance=2.0,
        angle_degrees=0.0,
    )

    assert result["moment"] == pytest.approx(0.0)


def test_equilibrium_force():
    result = statics(
        "equilibrium_force",
        fx_sum=30.0,
        fy_sum=-40.0,
    )

    assert result["fx"] == pytest.approx(-30.0)
    assert result["fy"] == pytest.approx(40.0)


def test_equilibrium_check_passes():
    result = statics(
        "equilibrium_check",
        fx_sum=0.0,
        fy_sum=0.0,
        moment_sum=0.0,
    )

    assert result["equilibrium"] is True
    assert result["force_equilibrium"] is True
    assert result["moment_equilibrium"] is True


def test_equilibrium_check_fails_force():
    result = statics(
        "equilibrium_check",
        fx_sum=1.0,
        fy_sum=0.0,
        moment_sum=0.0,
    )

    assert result["equilibrium"] is False
    assert result["force_equilibrium"] is False
    assert result["moment_equilibrium"] is True


def test_equilibrium_check_fails_moment():
    result = statics(
        "equilibrium_check",
        fx_sum=0.0,
        fy_sum=0.0,
        moment_sum=1.0,
    )

    assert result["equilibrium"] is False
    assert result["force_equilibrium"] is True
    assert result["moment_equilibrium"] is False


def test_invalid_operation_is_rejected():
    with pytest.raises(
        StaticsError,
        match="Unsupported statics operation",
    ):
        statics("not_real")


def test_missing_required_argument_is_rejected():
    with pytest.raises(
        StaticsError,
        match="magnitude",
    ):
        statics(
            "force_components",
            angle_degrees=30.0,
        )


def test_non_finite_input_is_rejected():
    with pytest.raises(
        StaticsError,
        match="finite",
    ):
        statics(
            "resultant_force",
            fx=float("inf"),
            fy=4.0,
        )


def test_force_magnitude_cannot_be_negative():
    with pytest.raises(
        StaticsError,
        match="magnitude",
    ):
        statics(
            "force_components",
            magnitude=-100.0,
            angle_degrees=30.0,
        )


def test_moment_distance_cannot_be_negative():
    with pytest.raises(
        StaticsError,
        match="perpendicular_distance",
    ):
        statics(
            "moment_from_force",
            force=100.0,
            perpendicular_distance=-2.0,
            angle_degrees=90.0,
        )
