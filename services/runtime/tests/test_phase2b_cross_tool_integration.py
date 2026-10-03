"""Phase 2B cross-tool production-path integration tests."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from anne_runtime.contracts import TaskRequest, TaskState
from anne_runtime.intelligence_contracts import IntelligenceToolProposal
from anne_runtime.runtime_application import RuntimeApplication


ROOT = Path(__file__).resolve().parents[3]


def _proposal(
    *,
    request_id,
    task_id,
    tool: str,
    operation: str,
    arguments: dict,
) -> IntelligenceToolProposal:
    return IntelligenceToolProposal(
        request_id=request_id,
        task_id=task_id,
        tool=tool,
        operation=operation,
        arguments=arguments,
    )


def _task_request(
    request_id,
    task_id,
    *,
    capability: str,
) -> TaskRequest:
    return TaskRequest(
        schema_version="1.0",
        request_id=request_id,
        task_id=task_id,
        created_at="2026-10-03T00:00:00Z",
        source="agent",
        user_intent="Run a chained engineering calculation through the production runtime.",
        priority="normal",
        workspace_id=uuid4(),
        requested_capabilities=(capability,),
        approval_required=False,
        approval_id=None,
        input_artifacts=(),
    )


def test_calculator_unit_convert_thermodynamics_production_path():
    """
    Verify a real registered engineering chain:

        calculator
            ↓
        unit conversion
            ↓
        thermodynamics

    Every tool executes through the real authority and TaskOrchestrator
    production execution path.
    """

    app = RuntimeApplication(ROOT)

    request_id = uuid4()
    task_id = uuid4()

    # ---------------------------------------------------------------
    # 1. Calculator
    # ---------------------------------------------------------------

    calculator_task = _task_request(
        request_id,
        task_id,
        capability="engineering.calculation",
    )

    calculator_proposal = _proposal(
        request_id=request_id,
        task_id=task_id,
        tool="anne.calculator",
        operation="run",
        arguments={
            "expression": "25 * 12",
        },
    )

    calculator_call = app._authority_resolver.resolve(
        calculator_proposal
    )

    calculator_outcome = app._task_orchestrator.run(
        calculator_task,
        calculator_call.call,
    )

    assert calculator_outcome.result is not None
    assert calculator_outcome.result.status.value == "SUCCEEDED"

    calculator_result = calculator_outcome.result.result

    assert calculator_result["expression"] == "25 * 12"
    assert calculator_result["value"] == pytest.approx(300.0)

    # ---------------------------------------------------------------
    # 2. Unit conversion
    #
    # Feed the calculator's actual output into the next tool.
    # ---------------------------------------------------------------

    converted_input = calculator_result["value"]

    conversion_task = _task_request(
        request_id,
        task_id,
        capability="engineering.unit_conversion",
    )

    conversion_proposal = _proposal(
        request_id=request_id,
        task_id=task_id,
        tool="anne.unit_convert",
        operation="run",
        arguments={
            "value": converted_input,
            "from_unit": "C",
            "to_unit": "K",
        },
    )

    conversion_call = app._authority_resolver.resolve(
        conversion_proposal
    )

    conversion_outcome = app._task_orchestrator.run(
        conversion_task,
        conversion_call.call,
    )

    assert conversion_outcome.result is not None
    assert conversion_outcome.result.status.value == "SUCCEEDED"

    conversion_result = conversion_outcome.result.result

    assert conversion_result["value"] == pytest.approx(300.0)
    assert conversion_result["from_unit"] == "C"
    assert conversion_result["to_unit"] == "K"
    assert conversion_result["result"] == pytest.approx(573.15)

    # ---------------------------------------------------------------
    # 3. Thermodynamics
    #
    # Feed the converted Kelvin temperature into the real
    # thermodynamics handler.
    # ---------------------------------------------------------------

    temperature_kelvin = conversion_result["result"]

    thermodynamics_task = _task_request(
        request_id,
        task_id,
        capability="engineering.thermodynamics",
    )

    thermodynamics_proposal = _proposal(
        request_id=request_id,
        task_id=task_id,
        tool="anne.thermodynamics",
        operation="run",
        arguments={
            "operation": "ideal_gas_pressure",
            "moles": 1.0,
            "gas_constant": 8.314462618,
            "temperature": temperature_kelvin,
            "volume": 0.024942,
        },
    )

    thermodynamics_call = app._authority_resolver.resolve(
        thermodynamics_proposal
    )

    thermodynamics_outcome = app._task_orchestrator.run(
        thermodynamics_task,
        thermodynamics_call.call,
    )

    assert thermodynamics_outcome.result is not None
    assert thermodynamics_outcome.result.status.value == "SUCCEEDED"

    thermodynamics_result = thermodynamics_outcome.result.result

    assert thermodynamics_result["operation"] == "ideal_gas_pressure"

    # nRT/V using the actual 573.15 K output from the conversion step.
    expected_pressure = (
        1.0
        * 8.314462618
        * temperature_kelvin
        / 0.024942
    )

    assert thermodynamics_result["pressure"] == pytest.approx(
        expected_pressure,
        rel=1e-6,
    )

    # ---------------------------------------------------------------
    # 4. Correlation must survive the entire chain.
    # ---------------------------------------------------------------

    for outcome in (
        calculator_outcome,
        conversion_outcome,
        thermodynamics_outcome,
    ):
        assert outcome.result is not None
        assert outcome.result.request_id == request_id
        assert outcome.result.task_id == task_id

    # ---------------------------------------------------------------
    # 5. Verify the production registry contains the real tools.
    # ---------------------------------------------------------------

    for tool_id in (
        "anne.calculator",
        "anne.unit_convert",
        "anne.thermodynamics",
    ):
        descriptor, handler = app._tool_registry.get(tool_id)

        assert descriptor.tool_id == tool_id
        assert handler is not None

    # ---------------------------------------------------------------
    # 6. Verify engineering metadata exists without exposing
    #    executable authority controls.
    # ---------------------------------------------------------------

    thermodynamics_descriptor = app._tool_registry.get(
        "anne.thermodynamics"
    )[0]

    assert "engineering.thermodynamics" in (
        thermodynamics_descriptor.capabilities
    )

    assert not hasattr(thermodynamics_descriptor, "handler")
    assert not hasattr(thermodynamics_descriptor, "execute")

def test_kinematics_dynamics_statics_production_path() -> None:
    """Verify a mechanics calculation chain through the production runtime."""

    app = RuntimeApplication(ROOT)

    request_id = uuid4()
    task_id = uuid4()

    # ---------------------------------------------------------------
    # 1. Kinematics: derive acceleration from velocity change.
    #
    # v_i = 2 m/s
    # v_f = 14 m/s
    # t   = 4 s
    #
    # a = (v_f - v_i) / t = 3 m/s^2
    # ---------------------------------------------------------------

    kinematics_proposal = _proposal(
        request_id=request_id,
        task_id=task_id,
        tool="anne.kinematics",
        operation="acceleration",
        arguments={
            "operation": "acceleration",
            "initial_velocity": 2.0,
            "final_velocity": 14.0,
            "time": 4.0,
        },
    )

    kinematics_task = _task_request(
        request_id,
        task_id,
        capability="engineering.kinematics",
    )

    kinematics_outcome = app._task_orchestrator.run(
        kinematics_task,
        app._authority_resolver.resolve(kinematics_proposal).call,
    )

    assert kinematics_outcome.state == TaskState.SUCCEEDED
    assert kinematics_outcome.result is not None

    acceleration = kinematics_outcome.result.result["result"]

    assert acceleration == pytest.approx(3.0)

    # ---------------------------------------------------------------
    # 2. Dynamics: use the kinematics acceleration to calculate force.
    #
    # m = 5 kg
    # F = m * a = 15 N
    # ---------------------------------------------------------------

    dynamics_proposal = _proposal(
        request_id=request_id,
        task_id=task_id,
        tool="anne.dynamics",
        operation="force",
        arguments={
            "operation": "force",
            "mass": 5.0,
            "acceleration": acceleration,
        },
    )

    dynamics_task = _task_request(
        request_id,
        task_id,
        capability="engineering.dynamics",
    )

    dynamics_outcome = app._task_orchestrator.run(
        dynamics_task,
        app._authority_resolver.resolve(dynamics_proposal).call,
    )

    assert dynamics_outcome.state == TaskState.SUCCEEDED, f"Dynamics failed: {dynamics_outcome!r}"
    assert dynamics_outcome.result is not None

    force = dynamics_outcome.result.result["result"]

    assert force == pytest.approx(15.0)

    # ---------------------------------------------------------------
    # 3. Statics: resolve the dynamics force into components and
    #    verify the resultant returns to the original force magnitude.
    #
    # F = 15 N
    # theta = 30 degrees
    # Fx = F cos(theta)
    # Fy = F sin(theta)
    # resultant = 15 N
    # ---------------------------------------------------------------

    statics_proposal = _proposal(
        request_id=request_id,
        task_id=task_id,
        tool="anne.statics",
        operation="force_components",
        arguments={
            "operation": "force_components",
            "magnitude": force,
            "angle_degrees": 30.0,
        },
    )

    statics_task = _task_request(
        request_id,
        task_id,
        capability="engineering.statics",
    )

    statics_outcome = app._task_orchestrator.run(
        statics_task,
        app._authority_resolver.resolve(statics_proposal).call,
    )

    assert statics_outcome.state == TaskState.SUCCEEDED
    assert statics_outcome.result is not None

    components = statics_outcome.result.result

    fx = components["fx"]
    fy = components["fy"]

    assert fx == pytest.approx(15.0 * (3.0 ** 0.5) / 2.0)
    assert fy == pytest.approx(7.5)

    # Feed the statics components into the resultant calculation.
    resultant_proposal = _proposal(
        request_id=request_id,
        task_id=task_id,
        tool="anne.statics",
        operation="resultant_force",
        arguments={
            "operation": "resultant_force",
            "fx": fx,
            "fy": fy,
        },
    )

    resultant_outcome = app._task_orchestrator.run(
        statics_task,
        app._authority_resolver.resolve(resultant_proposal).call,
    )

    assert resultant_outcome.state == TaskState.SUCCEEDED
    assert resultant_outcome.result is not None

    resultant = resultant_outcome.result.result["resultant"]

    assert resultant == pytest.approx(15.0)

    # ---------------------------------------------------------------
    # 4. Verify correlation survives the entire production chain.
    # ---------------------------------------------------------------

    for outcome in (
        kinematics_outcome,
        dynamics_outcome,
        statics_outcome,
        resultant_outcome,
    ):
        assert outcome.result is not None
        assert outcome.result.request_id == request_id
        assert outcome.result.task_id == task_id

    # ---------------------------------------------------------------
    # 5. Verify the production registry contains every tool used.
    # ---------------------------------------------------------------

    for tool_id in (
        "anne.kinematics",
        "anne.dynamics",
        "anne.statics",
    ):
        descriptor, handler = app._tool_registry.get(tool_id)

        assert descriptor.tool_id == tool_id
        assert handler is not None

    # ---------------------------------------------------------------
    # 6. Verify engineering capability metadata exists without
    #    exposing executable authority controls.
    # ---------------------------------------------------------------

    for tool_id, capability in (
        ("anne.kinematics", "engineering.kinematics"),
        ("anne.dynamics", "engineering.dynamics"),
        ("anne.statics", "engineering.statics"),
    ):
        descriptor = app._tool_registry.get(tool_id)[0]

        assert capability in descriptor.capabilities
        assert not hasattr(descriptor, "handler")
        assert not hasattr(descriptor, "execute")








def test_signal_processing_frequency_domain_production_path() -> None:
    """Verify signal-processing output feeds the frequency-domain tool."""

    app = RuntimeApplication(ROOT)

    request_id = uuid4()
    task_id = uuid4()

    # ---------------------------------------------------------------
    # 1. Signal processing: preserve an impulse with a window of 1.
    # ---------------------------------------------------------------

    signal_proposal = _proposal(
        request_id=request_id,
        task_id=task_id,
        tool="anne.signal_processing",
        operation="run",
        arguments={
            "operation": "moving_average",
            "values": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "window": 1,
        },
    )

    signal_task = _task_request(
        request_id,
        task_id,
        capability="engineering.signal_processing",
    )

    signal_outcome = app._task_orchestrator.run(
        signal_task,
        app._authority_resolver.resolve(signal_proposal).call,
    )

    assert signal_outcome.state == TaskState.SUCCEEDED
    assert signal_outcome.result is not None

    signal_result = signal_outcome.result.result

    assert signal_result["operation"] == "moving_average"
    processed_signal = signal_result["values"]

    assert processed_signal == pytest.approx(
        [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    )

    # ---------------------------------------------------------------
    # 2. Frequency domain: consume the actual signal-processing output.
    # ---------------------------------------------------------------

    frequency_proposal = _proposal(
        request_id=request_id,
        task_id=task_id,
        tool="anne.signal_processing.frequency_domain",
        operation="run",
        arguments={
            "operation": "magnitude_spectrum",
            "values": processed_signal,
            "sample_rate": 8.0,
        },
    )

    frequency_task = _task_request(
        request_id,
        task_id,
        capability="engineering.signal_processing.frequency_domain",
    )

    frequency_outcome = app._task_orchestrator.run(
        frequency_task,
        app._authority_resolver.resolve(frequency_proposal).call,
    )

    assert frequency_outcome.state == TaskState.SUCCEEDED
    assert frequency_outcome.result is not None

    frequency_result = frequency_outcome.result.result

    assert frequency_result["operation"] == "magnitude_spectrum"
    assert frequency_result["sample_rate"] == pytest.approx(8.0)

    frequencies = frequency_result["frequencies"]
    magnitudes = frequency_result["magnitudes"]

    # The implementation returns the complete 8-bin spectrum.
    assert frequencies == pytest.approx(
        [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    )
    assert magnitudes == pytest.approx(
        [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    )

    # ---------------------------------------------------------------
    # 3. Correlation must survive the entire chain.
    # ---------------------------------------------------------------

    for outcome in (
        signal_outcome,
        frequency_outcome,
    ):
        assert outcome.result is not None
        assert outcome.result.request_id == request_id
        assert outcome.result.task_id == task_id

    # ---------------------------------------------------------------
    # 4. Verify both tools are real production registrations.
    # ---------------------------------------------------------------

    for tool_id in (
        "anne.signal_processing",
        "anne.signal_processing.frequency_domain",
    ):
        descriptor, handler = app._tool_registry.get(tool_id)

        assert descriptor.tool_id == tool_id
        assert handler is not None

    # ---------------------------------------------------------------
    # 5. Verify engineering metadata without executable authority
    #    controls being exposed through the descriptor.
    # ---------------------------------------------------------------

    signal_descriptor = app._tool_registry.get(
        "anne.signal_processing"
    )[0]

    frequency_descriptor = app._tool_registry.get(
        "anne.signal_processing.frequency_domain"
    )[0]

    assert "engineering.signal_processing" in signal_descriptor.capabilities
    assert (
        "engineering.signal_processing.frequency_domain"
        in frequency_descriptor.capabilities
    )

    for descriptor in (
        signal_descriptor,
        frequency_descriptor,
    ):
        assert not hasattr(descriptor, "handler")
        assert not hasattr(descriptor, "execute")



def test_statistics_regression_interpolation_production_path() -> None:
    """Verify statistics output feeds regression, then interpolation."""

    app = RuntimeApplication(ROOT)

    request_id = uuid4()
    task_id = uuid4()

    # ---------------------------------------------------------------
    # 1. Statistics: calculate the mean of the x dataset.
    #
    # x = [0, 1, 2, 3]
    # mean(x) = 1.5
    # ---------------------------------------------------------------

    statistics_proposal = _proposal(
        request_id=request_id,
        task_id=task_id,
        tool="anne.statistics",
        operation="run",
        arguments={
            "operation": "mean",
            "values": [0.0, 1.0, 2.0, 3.0],
        },
    )

    statistics_task = _task_request(
        request_id,
        task_id,
        capability="engineering.statistics",
    )

    statistics_outcome = app._task_orchestrator.run(
        statistics_task,
        app._authority_resolver.resolve(statistics_proposal).call,
    )

    assert statistics_outcome.state == TaskState.SUCCEEDED
    assert statistics_outcome.result is not None

    statistics_result = statistics_outcome.result.result

    assert statistics_result["operation"] == "mean"

    mean_x = statistics_result["result"]

    assert mean_x == pytest.approx(1.5)

    # ---------------------------------------------------------------
    # 2. Regression: use the statistics mean as the prediction x.
    #
    # y = 2x
    # x = 1.5
    # prediction = 3.0
    # ---------------------------------------------------------------

    regression_proposal = _proposal(
        request_id=request_id,
        task_id=task_id,
        tool="anne.regression",
        operation="predict",
        arguments={
            "operation": "predict",
            "x_values": [0.0, 1.0, 2.0, 3.0],
            "y_values": [0.0, 2.0, 4.0, 6.0],
            "x": mean_x,
        },
    )

    regression_task = _task_request(
        request_id,
        task_id,
        capability="engineering.regression",
    )

    regression_outcome = app._task_orchestrator.run(
        regression_task,
        app._authority_resolver.resolve(regression_proposal).call,
    )

    assert regression_outcome.state == TaskState.SUCCEEDED
    assert regression_outcome.result is not None

    regression_result = regression_outcome.result.result

    assert regression_result["operation"] == "predict"

    predicted_x = regression_result["prediction"]

    assert predicted_x == pytest.approx(3.0)
    assert regression_result["slope"] == pytest.approx(2.0)
    assert regression_result["intercept"] == pytest.approx(0.0)
    assert regression_result["r_squared"] == pytest.approx(1.0)

    # ---------------------------------------------------------------
    # 3. Interpolation: use the regression prediction as the target x.
    #
    # Known data:
    # x = [0, 2, 4, 6]
    # y = [0, 4, 8, 12]
    #
    # target x = 3
    # interpolated y = 6
    # ---------------------------------------------------------------

    interpolation_proposal = _proposal(
        request_id=request_id,
        task_id=task_id,
        tool="anne.interpolation",
        operation="linear",
        arguments={
            "operation": "linear",
            "x_values": [0.0, 2.0, 4.0, 6.0],
            "y_values": [0.0, 4.0, 8.0, 12.0],
            "x": predicted_x,
        },
    )

    interpolation_task = _task_request(
        request_id,
        task_id,
        capability="engineering.interpolation",
    )

    interpolation_outcome = app._task_orchestrator.run(
        interpolation_task,
        app._authority_resolver.resolve(interpolation_proposal).call,
    )

    assert interpolation_outcome.state == TaskState.SUCCEEDED
    assert interpolation_outcome.result is not None

    interpolation_result = interpolation_outcome.result.result

    assert interpolation_result["operation"] == "linear"
    assert interpolation_result["result"] == pytest.approx(6.0)

    # ---------------------------------------------------------------
    # 4. Verify correlation survives the entire chain.
    # ---------------------------------------------------------------

    for outcome in (
        statistics_outcome,
        regression_outcome,
        interpolation_outcome,
    ):
        assert outcome.result is not None
        assert outcome.result.request_id == request_id
        assert outcome.result.task_id == task_id

    # ---------------------------------------------------------------
    # 5. Verify the production registry contains every tool used.
    # ---------------------------------------------------------------

    for tool_id in (
        "anne.statistics",
        "anne.regression",
        "anne.interpolation",
    ):
        descriptor, handler = app._tool_registry.get(tool_id)

        assert descriptor.tool_id == tool_id
        assert handler is not None

    # ---------------------------------------------------------------
    # 6. Verify engineering capability metadata exists without
    #    exposing executable authority controls.
    # ---------------------------------------------------------------

    for tool_id, capability in (
        ("anne.statistics", "engineering.statistics"),
        ("anne.regression", "engineering.regression"),
        ("anne.interpolation", "engineering.interpolation"),
    ):
        descriptor = app._tool_registry.get(tool_id)[0]

        assert capability in descriptor.capabilities
        assert not hasattr(descriptor, "handler")
        assert not hasattr(descriptor, "execute")

def test_circuit_analysis_signal_processing_production_path() -> None:
    """Verify circuit-analysis output feeds signal processing."""

    app = RuntimeApplication(ROOT)

    request_id = uuid4()
    task_id = uuid4()

    # ---------------------------------------------------------------
    # 1. Circuit analysis: calculate electrical power.
    #
    # V = 12 V
    # R = 6 ohms
    # I = V/R = 2 A
    # P = V^2/R = 24 W
    # ---------------------------------------------------------------

    circuit_proposal = _proposal(
        request_id=request_id,
        task_id=task_id,
        tool="anne.circuit_analysis",
        operation="run",
        arguments={
            "operation": "power",
            "voltage": 12.0,
            "resistance": 6.0,
        },
    )

    circuit_task = _task_request(
        request_id,
        task_id,
        capability="engineering.circuit_analysis",
    )

    circuit_outcome = app._task_orchestrator.run(
        circuit_task,
        app._authority_resolver.resolve(circuit_proposal).call,
    )

    assert circuit_outcome.state == TaskState.SUCCEEDED
    assert circuit_outcome.result is not None

    circuit_result = circuit_outcome.result.result

    assert circuit_result["operation"] == "power"
    assert circuit_result["power"] == pytest.approx(24.0)
    assert circuit_result["voltage"] == pytest.approx(12.0)
    assert circuit_result["current"] == pytest.approx(2.0)
    assert circuit_result["resistance"] == pytest.approx(6.0)

    circuit_power = circuit_result["power"]

    # ---------------------------------------------------------------
    # 2. Signal processing: consume the actual circuit output.
    #
    # The circuit-calculated power becomes the convolution kernel.
    #
    # input signal = [1, 2, 3]
    # kernel       = [24]
    #
    # output       = [24, 48, 72]
    # ---------------------------------------------------------------

    signal_proposal = _proposal(
        request_id=request_id,
        task_id=task_id,
        tool="anne.signal_processing",
        operation="run",
        arguments={
            "operation": "convolution",
            "values": [1.0, 2.0, 3.0],
            "kernel": [circuit_power],
        },
    )

    signal_task = _task_request(
        request_id,
        task_id,
        capability="engineering.signal_processing",
    )

    signal_outcome = app._task_orchestrator.run(
        signal_task,
        app._authority_resolver.resolve(signal_proposal).call,
    )

    assert signal_outcome.state == TaskState.SUCCEEDED
    assert signal_outcome.result is not None

    signal_result = signal_outcome.result.result

    assert signal_result["operation"] == "convolution"

    processed_signal = signal_result["values"]

    assert processed_signal == pytest.approx(
        [24.0, 48.0, 72.0]
    )

    # ---------------------------------------------------------------
    # 3. Verify correlation survives the entire chain.
    # ---------------------------------------------------------------

    for outcome in (
        circuit_outcome,
        signal_outcome,
    ):
        assert outcome.result is not None
        assert outcome.result.request_id == request_id
        assert outcome.result.task_id == task_id

    # ---------------------------------------------------------------
    # 4. Verify the production registry contains both tools.
    # ---------------------------------------------------------------

    for tool_id in (
        "anne.circuit_analysis",
        "anne.signal_processing",
    ):
        descriptor, handler = app._tool_registry.get(tool_id)

        assert descriptor.tool_id == tool_id
        assert handler is not None

    # ---------------------------------------------------------------
    # 5. Verify engineering capability metadata exists without
    #    exposing executable authority controls.
    # ---------------------------------------------------------------

    for tool_id, capability in (
        (
            "anne.circuit_analysis",
            "engineering.circuit_analysis",
        ),
        (
            "anne.signal_processing",
            "engineering.signal_processing",
        ),
    ):
        descriptor = app._tool_registry.get(tool_id)[0]

        assert capability in descriptor.capabilities
        assert not hasattr(descriptor, "handler")
        assert not hasattr(descriptor, "execute")

def test_fluid_mechanics_thermodynamics_production_path() -> None:
    """Verify fluid-mechanics pressure output feeds thermodynamics."""

    app = RuntimeApplication(ROOT)

    request_id = uuid4()
    task_id = uuid4()

    # ---------------------------------------------------------------
    # 1. Fluid mechanics: calculate absolute pressure.
    #
    # Gauge pressure      = 50,000 Pa
    # Atmospheric pressure = 101,325 Pa
    #
    # Absolute pressure = 151,325 Pa
    # ---------------------------------------------------------------

    fluid_proposal = _proposal(
        request_id=request_id,
        task_id=task_id,
        tool="anne.fluid_mechanics",
        operation="run",
        arguments={
            "operation": "absolute_pressure",
            "gauge_pressure": 50_000.0,
            "atmospheric_pressure": 101_325.0,
        },
    )

    fluid_task = _task_request(
        request_id,
        task_id,
        capability="engineering.fluid_mechanics",
    )

    fluid_outcome = app._task_orchestrator.run(
        fluid_task,
        app._authority_resolver.resolve(fluid_proposal).call,
    )

    assert fluid_outcome.state == TaskState.SUCCEEDED
    assert fluid_outcome.result is not None

    fluid_result = fluid_outcome.result.result

    assert fluid_result["operation"] == "absolute_pressure"
    assert fluid_result["pressure"] == pytest.approx(151_325.0)

    absolute_pressure = fluid_result["pressure"]

    # ---------------------------------------------------------------
    # 2. Thermodynamics: consume the actual fluid pressure.
    #
    # Ideal gas:
    #
    # V = nRT / P
    #
    # n = 1 mol
    # R = 8.314462618 J/(mol*K)
    # T = 300 K
    # P = fluid-calculated absolute pressure
    #
    # ---------------------------------------------------------------

    thermodynamics_proposal = _proposal(
        request_id=request_id,
        task_id=task_id,
        tool="anne.thermodynamics",
        operation="run",
        arguments={
            "operation": "ideal_gas_volume",
            "moles": 1.0,
            "gas_constant": 8.314462618,
            "temperature": 300.0,
            "pressure": absolute_pressure,
        },
    )

    thermodynamics_task = _task_request(
        request_id,
        task_id,
        capability="engineering.thermodynamics",
    )

    thermodynamics_outcome = app._task_orchestrator.run(
        thermodynamics_task,
        app._authority_resolver.resolve(thermodynamics_proposal).call,
    )

    assert thermodynamics_outcome.state == TaskState.SUCCEEDED
    assert thermodynamics_outcome.result is not None

    thermodynamics_result = thermodynamics_outcome.result.result

    assert thermodynamics_result["operation"] == "ideal_gas_volume"

    expected_volume = (
        1.0 * 8.314462618 * 300.0 / absolute_pressure
    )

    assert thermodynamics_result["volume"] == pytest.approx(
        expected_volume
    )

    # ---------------------------------------------------------------
    # 3. Verify correlation survives the entire chain.
    # ---------------------------------------------------------------

    for outcome in (
        fluid_outcome,
        thermodynamics_outcome,
    ):
        assert outcome.result is not None
        assert outcome.result.request_id == request_id
        assert outcome.result.task_id == task_id

    # ---------------------------------------------------------------
    # 4. Verify the production registry contains both tools.
    # ---------------------------------------------------------------

    for tool_id in (
        "anne.fluid_mechanics",
        "anne.thermodynamics",
    ):
        descriptor, handler = app._tool_registry.get(tool_id)

        assert descriptor.tool_id == tool_id
        assert handler is not None

    # ---------------------------------------------------------------
    # 5. Verify engineering capability metadata exists without
    #    exposing executable authority controls.
    # ---------------------------------------------------------------

    for tool_id, capability in (
        (
            "anne.fluid_mechanics",
            "engineering.fluid_mechanics",
        ),
        (
            "anne.thermodynamics",
            "engineering.thermodynamics",
        ),
    ):
        descriptor = app._tool_registry.get(tool_id)[0]

        assert capability in descriptor.capabilities
        assert not hasattr(descriptor, "handler")
        assert not hasattr(descriptor, "execute")
