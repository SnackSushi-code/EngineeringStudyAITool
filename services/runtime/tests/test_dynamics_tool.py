from __future__ import annotations

import math

import pytest

from anne_runtime.dynamics_tool import (
    DynamicsError,
    dynamics,
)


def test_force_from_mass_and_acceleration():
    result = dynamics(
        "force",
        mass=10.0,
        acceleration=3.0,
    )

    assert result["operation"] == "force"
    assert result["result"] == pytest.approx(30.0)


def test_mass_from_force_and_acceleration():
    result = dynamics(
        "mass_from_force",
        force=30.0,
        acceleration=3.0,
    )

    assert result["result"] == pytest.approx(10.0)


def test_acceleration_from_force_and_mass():
    result = dynamics(
        "acceleration_from_force",
        force=30.0,
        mass=10.0,
    )

    assert result["result"] == pytest.approx(3.0)


def test_weight():
    result = dynamics(
        "weight",
        mass=10.0,
        gravity=9.81,
    )

    assert result["result"] == pytest.approx(98.1)


def test_default_gravity_is_used():
    result = dynamics(
        "weight",
        mass=10.0,
    )

    assert result["result"] == pytest.approx(10.0 * 9.80665)


def test_momentum():
    result = dynamics(
        "momentum",
        mass=5.0,
        velocity=12.0,
    )

    assert result["result"] == pytest.approx(60.0)


def test_kinetic_energy():
    result = dynamics(
        "kinetic_energy",
        mass=10.0,
        velocity=4.0,
    )

    assert result["result"] == pytest.approx(80.0)


def test_potential_energy():
    result = dynamics(
        "potential_energy",
        mass=10.0,
        height=5.0,
        gravity=9.81,
    )

    assert result["result"] == pytest.approx(490.5)


def test_work_with_zero_angle():
    result = dynamics(
        "work",
        force=20.0,
        displacement=5.0,
        angle_degrees=0.0,
    )

    assert result["result"] == pytest.approx(100.0)


def test_work_with_ninety_degree_angle():
    result = dynamics(
        "work",
        force=20.0,
        displacement=5.0,
        angle_degrees=90.0,
    )

    assert result["result"] == pytest.approx(0.0, abs=1e-12)


def test_power():
    result = dynamics(
        "power",
        work=500.0,
        time=10.0,
    )

    assert result["result"] == pytest.approx(50.0)


def test_invalid_operation_is_rejected():
    with pytest.raises(
        DynamicsError,
        match="Unsupported dynamics operation",
    ):
        dynamics("not_real")


def test_missing_required_argument_is_rejected():
    with pytest.raises(DynamicsError, match="mass"):
        dynamics(
            "force",
            acceleration=3.0,
        )


def test_zero_mass_is_rejected():
    with pytest.raises(DynamicsError, match="mass"):
        dynamics(
            "acceleration_from_force",
            force=30.0,
            mass=0.0,
        )


def test_zero_acceleration_is_rejected_for_mass():
    with pytest.raises(DynamicsError, match="acceleration"):
        dynamics(
            "mass_from_force",
            force=30.0,
            acceleration=0.0,
        )


def test_zero_time_is_rejected_for_power():
    with pytest.raises(DynamicsError, match="time"):
        dynamics(
            "power",
            work=500.0,
            time=0.0,
        )


def test_negative_mass_is_rejected():
    with pytest.raises(DynamicsError, match="mass"):
        dynamics(
            "force",
            mass=-10.0,
            acceleration=3.0,
        )


def test_negative_gravity_is_rejected():
    with pytest.raises(DynamicsError, match="gravity"):
        dynamics(
            "weight",
            mass=10.0,
            gravity=-9.81,
        )


def test_non_finite_input_is_rejected():
    with pytest.raises(DynamicsError, match="finite"):
        dynamics(
            "force",
            mass=float("inf"),
            acceleration=3.0,
        )


def test_angle_out_of_range_is_rejected():
    with pytest.raises(DynamicsError, match="angle_degrees"):
        dynamics(
            "work",
            force=20.0,
            displacement=5.0,
            angle_degrees=181.0,
        )
