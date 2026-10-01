from __future__ import annotations

import math

import pytest

from anne_runtime.kinematics_tool import (
    KinematicsError,
    kinematics,
)


def test_velocity_from_initial_velocity_acceleration_and_time():
    result = kinematics(
        "velocity",
        initial_velocity=5.0,
        acceleration=2.0,
        time=4.0,
    )

    assert result["operation"] == "velocity"
    assert result["result"] == pytest.approx(13.0)


def test_displacement_from_initial_velocity_acceleration_and_time():
    result = kinematics(
        "displacement",
        initial_velocity=5.0,
        acceleration=2.0,
        time=4.0,
    )

    assert result["operation"] == "displacement"
    assert result["result"] == pytest.approx(36.0)


def test_final_velocity_from_displacement():
    result = kinematics(
        "final_velocity_from_displacement",
        initial_velocity=3.0,
        acceleration=4.0,
        displacement=8.0,
    )

    assert result["result"] == pytest.approx(math.sqrt(73.0))


def test_acceleration_from_velocity_change():
    result = kinematics(
        "acceleration",
        initial_velocity=4.0,
        final_velocity=16.0,
        time=3.0,
    )

    assert result["result"] == pytest.approx(4.0)


def test_time_from_velocity_change():
    result = kinematics(
        "time_from_velocity",
        initial_velocity=4.0,
        final_velocity=16.0,
        acceleration=3.0,
    )

    assert result["result"] == pytest.approx(4.0)


def test_projectile_time_of_flight():
    result = kinematics(
        "projectile_time",
        initial_speed=20.0,
        launch_angle_degrees=30.0,
        gravity=9.81,
    )

    expected = (2.0 * 20.0 * math.sin(math.radians(30.0))) / 9.81

    assert result["result"] == pytest.approx(expected)


def test_projectile_range():
    result = kinematics(
        "projectile_range",
        initial_speed=20.0,
        launch_angle_degrees=45.0,
        gravity=9.81,
    )

    expected = (20.0**2 * math.sin(math.radians(90.0))) / 9.81

    assert result["result"] == pytest.approx(expected)


def test_projectile_max_height():
    result = kinematics(
        "projectile_max_height",
        initial_speed=20.0,
        launch_angle_degrees=30.0,
        gravity=9.81,
    )

    expected = (
        20.0**2
        * math.sin(math.radians(30.0))**2
        / (2.0 * 9.81)
    )

    assert result["result"] == pytest.approx(expected)


def test_default_gravity_is_used():
    result = kinematics(
        "projectile_time",
        initial_speed=10.0,
        launch_angle_degrees=90.0,
    )

    expected = 20.0 / 9.80665

    assert result["result"] == pytest.approx(expected)


def test_invalid_operation_is_rejected():
    with pytest.raises(KinematicsError, match="Unsupported kinematics operation"):
        kinematics("not_real")


def test_missing_required_argument_is_rejected():
    with pytest.raises(KinematicsError, match="initial_velocity"):
        kinematics(
            "velocity",
            acceleration=2.0,
            time=4.0,
        )


def test_zero_acceleration_is_rejected_for_time_from_velocity():
    with pytest.raises(KinematicsError, match="acceleration"):
        kinematics(
            "time_from_velocity",
            initial_velocity=4.0,
            final_velocity=16.0,
            acceleration=0.0,
        )


def test_negative_gravity_is_rejected():
    with pytest.raises(KinematicsError, match="gravity"):
        kinematics(
            "projectile_time",
            initial_speed=20.0,
            launch_angle_degrees=30.0,
            gravity=-9.81,
        )


def test_negative_initial_speed_is_rejected():
    with pytest.raises(KinematicsError, match="initial_speed"):
        kinematics(
            "projectile_range",
            initial_speed=-20.0,
            launch_angle_degrees=45.0,
        )


def test_non_finite_input_is_rejected():
    with pytest.raises(KinematicsError, match="finite"):
        kinematics(
            "velocity",
            initial_velocity=float("inf"),
            acceleration=2.0,
            time=4.0,
        )
