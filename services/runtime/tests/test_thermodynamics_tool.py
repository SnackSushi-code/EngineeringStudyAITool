import math

import pytest

from anne_runtime.thermodynamics_tool import ThermodynamicsError
from anne_runtime.thermodynamics_tool import thermodynamics


def test_ideal_gas_pressure():
    result = thermodynamics(
        "ideal_gas_pressure",
        moles=1.0,
        gas_constant=8.314462618,
        temperature=300.0,
        volume=0.0249433878544594,
    )

    assert result["pressure"] == pytest.approx(100000.0, rel=1e-6)


def test_ideal_gas_volume():
    result = thermodynamics(
        "ideal_gas_volume",
        moles=1.0,
        gas_constant=8.314462618,
        temperature=300.0,
        pressure=100000.0,
    )

    assert result["volume"] == pytest.approx(0.0249434, rel=1e-5)


def test_ideal_gas_temperature():
    result = thermodynamics(
        "ideal_gas_temperature",
        pressure=100000.0,
        volume=0.0249434,
        moles=1.0,
        gas_constant=8.314462618,
    )

    assert result["temperature"] == pytest.approx(300.0, rel=1e-5)


def test_ideal_gas_moles():
    result = thermodynamics(
        "ideal_gas_moles",
        pressure=100000.0,
        volume=0.0249434,
        gas_constant=8.314462618,
        temperature=300.0,
    )

    assert result["moles"] == pytest.approx(1.0, rel=1e-5)


def test_density_ideal_gas():
    result = thermodynamics(
        "density_ideal_gas",
        pressure=101325.0,
        molar_mass=0.02897,
        gas_constant=8.314462618,
        temperature=300.0,
    )

    assert result["density"] == pytest.approx(1.1766, rel=1e-3)


def test_specific_gas_constant():
    result = thermodynamics(
        "specific_gas_constant",
        universal_gas_constant=8.314462618,
        molar_mass=0.02897,
    )

    assert result["specific_gas_constant"] == pytest.approx(
        287.0,
        rel=1e-3,
    )


def test_heat_transfer():
    result = thermodynamics(
        "heat_transfer",
        mass=2.0,
        specific_heat=4186.0,
        temperature_change=10.0,
    )

    assert result["heat"] == pytest.approx(83720.0)


def test_sensible_heat():
    result = thermodynamics(
        "sensible_heat",
        mass=2.0,
        specific_heat_capacity=4186.0,
        temperature_change=10.0,
    )

    assert result["heat"] == pytest.approx(83720.0)


def test_latent_heat():
    result = thermodynamics(
        "latent_heat",
        mass=2.0,
        latent_heat=334000.0,
    )

    assert result["heat"] == pytest.approx(668000.0)


def test_thermal_efficiency():
    result = thermodynamics(
        "thermal_efficiency",
        work_output=300.0,
        heat_input=1000.0,
    )

    assert result["efficiency"] == pytest.approx(0.3)


def test_refrigerator_cop():
    result = thermodynamics(
        "coefficient_of_performance_refrigerator",
        cooling_effect=1200.0,
        work_input=300.0,
    )

    assert result["cop"] == pytest.approx(4.0)


def test_heat_pump_cop():
    result = thermodynamics(
        "coefficient_of_performance_heat_pump",
        heating_effect=1500.0,
        work_input=300.0,
    )

    assert result["cop"] == pytest.approx(5.0)


def test_first_law_closed_system():
    result = thermodynamics(
        "first_law_closed_system",
        heat_transfer=500.0,
        work_output=200.0,
    )

    assert result["change_internal_energy"] == pytest.approx(300.0)


def test_entropy_change():
    result = thermodynamics(
        "entropy_change",
        mass=2.0,
        specific_heat=1000.0,
        temperature_initial=300.0,
        temperature_final=600.0,
    )

    assert result["entropy_change"] == pytest.approx(
        2.0 * 1000.0 * math.log(2.0)
    )


def test_zero_heat_transfer_allowed():
    result = thermodynamics(
        "heat_transfer",
        mass=2.0,
        specific_heat=1000.0,
        temperature_change=0.0,
    )

    assert result["heat"] == 0.0


def test_zero_work_rejected_for_efficiency():
    with pytest.raises(ThermodynamicsError):
        thermodynamics(
            "thermal_efficiency",
            work_output=300.0,
            heat_input=0.0,
        )


def test_zero_molar_mass_rejected():
    with pytest.raises(ThermodynamicsError):
        thermodynamics(
            "specific_gas_constant",
            universal_gas_constant=8.314462618,
            molar_mass=0.0,
        )


def test_zero_volume_rejected():
    with pytest.raises(ThermodynamicsError):
        thermodynamics(
            "ideal_gas_pressure",
            moles=1.0,
            gas_constant=8.314462618,
            temperature=300.0,
            volume=0.0,
        )


def test_negative_absolute_temperature_rejected():
    with pytest.raises(ThermodynamicsError):
        thermodynamics(
            "ideal_gas_pressure",
            moles=1.0,
            gas_constant=8.314462618,
            temperature=-10.0,
            volume=1.0,
        )


def test_invalid_operation_rejected():
    with pytest.raises(ThermodynamicsError):
        thermodynamics("not_a_real_operation")


def test_non_finite_input_rejected():
    with pytest.raises(ThermodynamicsError):
        thermodynamics(
            "heat_transfer",
            mass=float("nan"),
            specific_heat=1000.0,
            temperature_change=10.0,
        )


def test_excessive_input_rejected():
    with pytest.raises(ThermodynamicsError):
        thermodynamics(
            "heat_transfer",
            mass=1e101,
            specific_heat=1000.0,
            temperature_change=10.0,
        )
