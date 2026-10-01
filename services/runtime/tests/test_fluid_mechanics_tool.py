from __future__ import annotations

import math

import pytest

from anne_runtime.fluid_mechanics_tool import (
    FluidMechanicsError,
    fluid_mechanics,
)


def test_pressure():
    result = fluid_mechanics(
        "pressure",
        force=100.0,
        area=2.0,
    )

    assert result["operation"] == "pressure"
    assert result["pressure"] == pytest.approx(50.0)


def test_hydrostatic_pressure():
    result = fluid_mechanics(
        "hydrostatic_pressure",
        density=1000.0,
        gravity=9.80665,
        depth=2.0,
    )

    assert result["pressure"] == pytest.approx(19613.3)


def test_absolute_pressure():
    result = fluid_mechanics(
        "absolute_pressure",
        gauge_pressure=50000.0,
        atmospheric_pressure=101325.0,
    )

    assert result["pressure"] == pytest.approx(151325.0)


def test_gauge_pressure():
    result = fluid_mechanics(
        "gauge_pressure",
        absolute_pressure=151325.0,
        atmospheric_pressure=101325.0,
    )

    assert result["pressure"] == pytest.approx(50000.0)


def test_density():
    result = fluid_mechanics(
        "density",
        mass=10.0,
        volume=2.0,
    )

    assert result["density"] == pytest.approx(5.0)


def test_specific_weight():
    result = fluid_mechanics(
        "specific_weight",
        density=1000.0,
        gravity=9.80665,
    )

    assert result["specific_weight"] == pytest.approx(9806.65)


def test_continuity():
    result = fluid_mechanics(
        "continuity",
        area_1=2.0,
        velocity_1=3.0,
        area_2=1.0,
    )

    assert result["velocity_2"] == pytest.approx(6.0)


def test_volumetric_flow_rate():
    result = fluid_mechanics(
        "volumetric_flow_rate",
        area=2.0,
        velocity=3.0,
    )

    assert result["flow_rate"] == pytest.approx(6.0)


def test_mass_flow_rate():
    result = fluid_mechanics(
        "mass_flow_rate",
        density=1000.0,
        volumetric_flow_rate=0.5,
    )

    assert result["mass_flow_rate"] == pytest.approx(500.0)


def test_dynamic_pressure():
    result = fluid_mechanics(
        "dynamic_pressure",
        density=1000.0,
        velocity=10.0,
    )

    assert result["dynamic_pressure"] == pytest.approx(50000.0)


def test_reynolds_number():
    result = fluid_mechanics(
        "reynolds_number",
        density=1000.0,
        velocity=2.0,
        characteristic_length=0.1,
        dynamic_viscosity=0.001,
    )

    assert result["reynolds_number"] == pytest.approx(200000.0)


def test_hydraulic_power():
    result = fluid_mechanics(
        "hydraulic_power",
        density=1000.0,
        gravity=9.80665,
        volumetric_flow_rate=0.1,
        head=10.0,
    )

    assert result["power"] == pytest.approx(9806.65)


def test_buoyant_force():
    result = fluid_mechanics(
        "buoyant_force",
        density=1000.0,
        gravity=9.80665,
        displaced_volume=0.02,
    )

    assert result["buoyant_force"] == pytest.approx(196.133)


def test_bernoulli_velocity():
    result = fluid_mechanics(
        "bernoulli_velocity",
        pressure_1=200000.0,
        pressure_2=100000.0,
        density=1000.0,
        velocity_1=5.0,
        elevation_1=10.0,
        elevation_2=0.0,
        gravity=9.80665,
    )

    expected = math.sqrt(
        5.0**2
        + 2.0 * (
            (200000.0 - 100000.0) / 1000.0
            + 9.80665 * (10.0 - 0.0)
        )
    )

    assert result["velocity_2"] == pytest.approx(expected)


def test_pressure_allows_zero_force():
    result = fluid_mechanics(
        "pressure",
        force=0.0,
        area=2.0,
    )

    assert result["pressure"] == pytest.approx(0.0)


def test_pressure_rejects_zero_area():
    with pytest.raises(
        FluidMechanicsError,
        match="area",
    ):
        fluid_mechanics(
            "pressure",
            force=100.0,
            area=0.0,
        )


def test_density_rejects_negative_volume():
    with pytest.raises(
        FluidMechanicsError,
        match="volume",
    ):
        fluid_mechanics(
            "density",
            mass=10.0,
            volume=-2.0,
        )


def test_invalid_operation_is_rejected():
    with pytest.raises(
        FluidMechanicsError,
        match="Unsupported fluid mechanics operation",
    ):
        fluid_mechanics("not_real")


def test_missing_required_argument_is_rejected():
    with pytest.raises(
        FluidMechanicsError,
        match="force",
    ):
        fluid_mechanics(
            "pressure",
            area=2.0,
        )


def test_non_finite_input_is_rejected():
    with pytest.raises(
        FluidMechanicsError,
        match="finite",
    ):
        fluid_mechanics(
            "density",
            mass=float("inf"),
            volume=2.0,
        )


def test_excessive_input_is_rejected():
    with pytest.raises(
        FluidMechanicsError,
        match="maximum supported magnitude",
    ):
        fluid_mechanics(
            "pressure",
            force=1e101,
            area=2.0,
        )


def test_reynolds_number_rejects_zero_viscosity():
    with pytest.raises(
        FluidMechanicsError,
        match="dynamic_viscosity",
    ):
        fluid_mechanics(
            "reynolds_number",
            density=1000.0,
            velocity=2.0,
            characteristic_length=0.1,
            dynamic_viscosity=0.0,
        )


def test_bernoulli_rejects_negative_velocity_squared():
    with pytest.raises(
        FluidMechanicsError,
        match="velocity",
    ):
        fluid_mechanics(
            "bernoulli_velocity",
            pressure_1=0.0,
            pressure_2=1000000.0,
            density=1000.0,
            velocity_1=0.0,
            elevation_1=0.0,
            elevation_2=0.0,
            gravity=9.80665,
        )
