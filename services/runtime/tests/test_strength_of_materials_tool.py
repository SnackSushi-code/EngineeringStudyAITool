"""Tests for the deterministic engineering strength-of-materials tool."""

import math

import pytest

from anne_runtime.strength_of_materials_tool import (
    StrengthOfMaterialsError,
    strength_of_materials,
)


def test_normal_stress():
    result = strength_of_materials(
        "normal_stress",
        force=1000,
        area=0.01,
    )
    assert result["operation"] == "normal_stress"
    assert result["stress"] == pytest.approx(100000)


def test_shear_stress():
    result = strength_of_materials(
        "shear_stress",
        force=500,
        area=0.005,
    )
    assert result["stress"] == pytest.approx(100000)


def test_strain():
    result = strength_of_materials(
        "strain",
        elongation=0.002,
        original_length=1.0,
    )
    assert result["strain"] == pytest.approx(0.002)


def test_elongation():
    result = strength_of_materials(
        "elongation",
        force=1000,
        length=2.0,
        area=0.001,
        youngs_modulus=200e9,
    )
    assert result["elongation"] == pytest.approx(1e-5)


def test_hookes_law():
    result = strength_of_materials(
        "hookes_law",
        youngs_modulus=200e9,
        strain=0.001,
    )
    assert result["stress"] == pytest.approx(200e6)


def test_youngs_modulus():
    result = strength_of_materials(
        "youngs_modulus",
        stress=200e6,
        strain=0.001,
    )
    assert result["youngs_modulus"] == pytest.approx(200e9)


def test_factor_of_safety():
    result = strength_of_materials(
        "factor_of_safety",
        failure_stress=400e6,
        working_stress=100e6,
    )
    assert result["factor_of_safety"] == pytest.approx(4.0)


def test_thermal_strain():
    result = strength_of_materials(
        "thermal_strain",
        coefficient_of_expansion=12e-6,
        temperature_change=50,
    )
    assert result["strain"] == pytest.approx(0.0006)


def test_thermal_expansion():
    result = strength_of_materials(
        "thermal_expansion",
        coefficient_of_expansion=12e-6,
        length=2.0,
        temperature_change=50,
    )
    assert result["elongation"] == pytest.approx(0.0012)


def test_bending_stress():
    result = strength_of_materials(
        "bending_stress",
        moment=1000,
        distance_from_neutral_axis=0.05,
        area_moment_of_inertia=0.0001,
    )
    assert result["stress"] == pytest.approx(500000)


def test_beam_shear_stress():
    result = strength_of_materials(
        "beam_shear_stress",
        shear_force=1000,
        first_moment_area=0.00001,
        area_moment_of_inertia=0.0001,
        thickness=0.01,
    )
    assert result["stress"] == pytest.approx(10000)


def test_normal_stress_zero_force():
    result = strength_of_materials(
        "normal_stress",
        force=0,
        area=0.01,
    )
    assert result["stress"] == pytest.approx(0)


def test_negative_force_is_allowed_for_signed_normal_stress():
    result = strength_of_materials(
        "normal_stress",
        force=-1000,
        area=0.01,
    )
    assert result["stress"] == pytest.approx(-100000)


def test_invalid_operation_is_rejected():
    with pytest.raises(StrengthOfMaterialsError, match="Unsupported"):
        strength_of_materials("not_an_operation")


def test_missing_required_argument_is_rejected():
    with pytest.raises(StrengthOfMaterialsError, match="Missing required"):
        strength_of_materials("normal_stress", force=1000)


def test_zero_area_is_rejected():
    with pytest.raises(StrengthOfMaterialsError, match="greater than zero"):
        strength_of_materials(
            "normal_stress",
            force=1000,
            area=0,
        )


def test_negative_area_is_rejected():
    with pytest.raises(StrengthOfMaterialsError, match="greater than zero"):
        strength_of_materials(
            "normal_stress",
            force=1000,
            area=-1,
        )


def test_non_finite_input_is_rejected():
    with pytest.raises(StrengthOfMaterialsError, match="finite"):
        strength_of_materials(
            "normal_stress",
            force=math.inf,
            area=1,
        )


def test_excessive_input_is_rejected():
    with pytest.raises(StrengthOfMaterialsError, match="magnitude"):
        strength_of_materials(
            "normal_stress",
            force=1e101,
            area=1,
        )


def test_zero_strain_rejected_for_youngs_modulus():
    with pytest.raises(StrengthOfMaterialsError, match="greater than zero"):
        strength_of_materials(
            "youngs_modulus",
            stress=100,
            strain=0,
        )
