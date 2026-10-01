from __future__ import annotations

import json

from pathlib import Path
from uuid import uuid4

import pytest

from anne_runtime.runtime_application import (
    RuntimeApplication,
    RuntimeApplicationError,
)


@pytest.fixture(autouse=True)
def force_deterministic_provider(monkeypatch):
    """
    Keep RuntimeApplication tests deterministic and offline.

    The production application intentionally honors ANNE_MODEL_PROVIDER.
    Tests must not inherit a developer's local provider selection because
    that could cause an external model/API request during the test suite.
    """
    monkeypatch.setenv("ANNE_MODEL_PROVIDER", "deterministic")
    monkeypatch.setenv("ANNE_MODEL_NAME", "deterministic-v1")


def test_message_traverses_intelligence_pipeline(tmp_path):
    repository_root = tmp_path

    schema_dir = repository_root / "packages" / "schemas"
    schema_dir.mkdir(parents=True)

    application = RuntimeApplication(
        repository_root=repository_root,
    )

    request_id = str(uuid4())
    task_id = str(uuid4())

    result = application.handle_message(
        request_id=request_id,
        task_id=task_id,
        payload={
            "user_intent": "Explain an STM32 GPIO input.",
            "conversation": [],
        },
    )

    assert result["stop_reason"] == "FINAL_RESPONSE"
    assert result["iterations"] == 1
    assert result["provider_id"] == "deterministic"
    assert result["provider_version"] == "1.0.0"
    assert result["model"] == "deterministic-v1"

    response_text = result["response_text"]

    assert isinstance(response_text, str)
    assert "Explain an STM32 GPIO input." in response_text
    assert "IntelligenceRequest" in response_text
    assert "IntelligenceOrchestrator" in response_text
    assert "ModelService" in response_text
    assert "IntelligencePlanningLoop" in response_text


def test_message_executes_calculator_through_production_path(tmp_path, monkeypatch):
    repository_root = Path(__file__).resolve().parents[3]

    def calculator_responder(model_request):
        if len(model_request.messages) == 1:
            return json.dumps(
                {
                    "contract_version": "1.0",
                    "decision_type": "TOOL_PROPOSAL",
                    "tool_call": {
                        "request_id": str(request_id),
                        "task_id": str(task_id),
                        "tool": "anne.calculator",
                        "operation": "run",
                        "arguments": {
                            "expression": "9.81 * 5",
                        },
                    },
                }
            )

        assert len(model_request.messages) == 3
        tool_message = model_request.messages[2]

        assert tool_message.role.value == "tool"
        assert tool_message.name == "anne.calculator"
        assert '"value": 49.050000000000004' in tool_message.content

        return json.dumps(
            {
                "contract_version": "1.0",
                "decision_type": "FINAL_RESPONSE",
                "response_text": "The calculation result is 49.05.",
            }
        )

    monkeypatch.setattr(
        RuntimeApplication,
        "_deterministic_responder",
        staticmethod(calculator_responder),
    )

    application = RuntimeApplication(
        repository_root=repository_root,
    )

    request_id = str(uuid4())
    task_id = str(uuid4())

    result = application.handle_message(
        request_id=request_id,
        task_id=task_id,
        payload={
            "user_intent": "Calculate 9.81 * 5.",
            "conversation": [],
        },
    )

    assert result["stop_reason"] == "FINAL_RESPONSE"
    assert result["iterations"] == 2
    assert result["provider_id"] == "deterministic"
    assert result["provider_version"] == "1.0.0"
    assert result["model"] == "deterministic-v1"
    assert result["response_text"] == "The calculation result is 49.05."


def test_message_rejects_blank_user_intent(tmp_path):
    schema_dir = tmp_path / "packages" / "schemas"
    schema_dir.mkdir(parents=True)

    application = RuntimeApplication(
        repository_root=tmp_path,
    )

    with pytest.raises(
        RuntimeApplicationError,
        match="user_intent must not be blank",
    ):
        application.handle_message(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            payload={
                "user_intent": "   ",
                "conversation": [],
            },
        )


def test_message_rejects_invalid_conversation(tmp_path):
    schema_dir = tmp_path / "packages" / "schemas"
    schema_dir.mkdir(parents=True)

    application = RuntimeApplication(
        repository_root=tmp_path,
    )

    with pytest.raises(
        RuntimeApplicationError,
        match="conversation entry 0",
    ):
        application.handle_message(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            payload={
                "user_intent": "Hello Ann-E.",
                "conversation": [
                    {
                        "role": "assistant",
                    }
                ],
            },
        )
def test_message_executes_unit_conversion_through_production_path(tmp_path, monkeypatch):
    repository_root = Path(__file__).resolve().parents[3]

    def unit_conversion_responder(model_request):
        if len(model_request.messages) == 1:
            return json.dumps(
                {
                    "contract_version": "1.0",
                    "decision_type": "TOOL_PROPOSAL",
                    "response_text": None,
                    "tool_call": {
                        "request_id": str(request_id),
                        "task_id": str(task_id),
                        "tool": "anne.unit_convert",
                        "operation": "run",
                        "arguments": {
                            "value": 12,
                            "from_unit": "in",
                            "to_unit": "ft",
                        },
                    },
                }
            )

        assert len(model_request.messages) == 3
        tool_message = model_request.messages[2]

        assert tool_message.role.value == "tool"
        assert tool_message.name == "anne.unit_convert"
        assert '"result": 1.0' in tool_message.content

        return json.dumps(
            {
                "contract_version": "1.0",
                "decision_type": "FINAL_RESPONSE",
                "response_text": "12 inches is exactly 1 foot.",
            }
        )

    monkeypatch.setattr(
        RuntimeApplication,
        "_deterministic_responder",
        staticmethod(unit_conversion_responder),
    )

    application = RuntimeApplication(
        repository_root=repository_root,
    )

    request_id = str(uuid4())
    task_id = str(uuid4())

    result = application.handle_message(
        request_id=request_id,
        task_id=task_id,
        payload={
            "user_intent": "Convert 12 inches to feet.",
            "conversation": [],
        },
    )

    assert result["stop_reason"] == "FINAL_RESPONSE"
    assert result["iterations"] == 2
    assert result["provider_id"] == "deterministic"
    assert result["provider_version"] == "1.0.0"
    assert result["model"] == "deterministic-v1"
    assert result["response_text"] == "12 inches is exactly 1 foot."

def test_message_executes_vector_math_through_production_path(tmp_path, monkeypatch):
    repository_root = Path(__file__).resolve().parents[3]

    def vector_math_responder(model_request):
        if len(model_request.messages) == 1:
            return json.dumps(
                {
                    "contract_version": "1.0",
                    "decision_type": "TOOL_PROPOSAL",
                    "response_text": None,
                    "tool_call": {
                        "request_id": str(request_id),
                        "task_id": str(task_id),
                        "tool": "anne.vector_math",
                        "operation": "run",
                        "arguments": {
                            "operation": "magnitude",
                            "vector": [3, 4],
                        },
                    },
                }
            )

        assert len(model_request.messages) == 3
        tool_message = model_request.messages[2]

        assert tool_message.role.value == "tool"
        assert tool_message.name == "anne.vector_math"
        assert '"result": 5.0' in tool_message.content

        return json.dumps(
            {
                "contract_version": "1.0",
                "decision_type": "FINAL_RESPONSE",
                "response_text": "The vector magnitude is 5.",
            }
        )

    monkeypatch.setattr(
        RuntimeApplication,
        "_deterministic_responder",
        staticmethod(vector_math_responder),
    )

    application = RuntimeApplication(
        repository_root=repository_root,
    )

    request_id = str(uuid4())
    task_id = str(uuid4())

    result = application.handle_message(
        request_id=request_id,
        task_id=task_id,
        payload={
            "user_intent": "Calculate the magnitude of vector [3, 4].",
            "conversation": [],
        },
    )

    assert result["stop_reason"] == "FINAL_RESPONSE"
    assert result["iterations"] == 2
    assert result["provider_id"] == "deterministic"
    assert result["provider_version"] == "1.0.0"
    assert result["model"] == "deterministic-v1"
    assert result["response_text"] == "The vector magnitude is 5."
def test_message_executes_matrix_math_through_production_path(
    tmp_path,
    monkeypatch,
):
    repository_root = Path(__file__).resolve().parents[3]

    request_id = str(uuid4())
    task_id = str(uuid4())

    def matrix_math_responder(model_request):
        if len(model_request.messages) == 1:
            return json.dumps(
                {
                    "contract_version": "1.0",
                    "decision_type": "TOOL_PROPOSAL",
                    "response_text": None,
                    "tool_call": {
                        "request_id": request_id,
                        "task_id": task_id,
                        "tool": "anne.matrix_math",
                        "operation": "run",
                        "arguments": {
                            "operation": "multiply",
                            "left": [[1, 2], [3, 4]],
                            "right": [[5, 6], [7, 8]],
                        },
                    },
                }
            )

        assert len(model_request.messages) == 3

        tool_message = model_request.messages[2]

        assert tool_message.role.value == "tool"
        assert tool_message.name == "anne.matrix_math"
        assert '"result": [[19.0, 22.0], [43.0, 50.0]]' in tool_message.content

        return json.dumps(
            {
                "contract_version": "1.0",
                "decision_type": "FINAL_RESPONSE",
                "response_text": "The matrix product is [[19, 22], [43, 50]].",
                "tool_call": None,
            }
        )

    monkeypatch.setattr(
        RuntimeApplication,
        "_deterministic_responder",
        staticmethod(matrix_math_responder),
    )

    application = RuntimeApplication(
        repository_root=repository_root,
    )

    result = application.handle_message(
        request_id=request_id,
        task_id=task_id,
        payload={
            "user_intent": (
                "Multiply the matrices [[1, 2], [3, 4]] "
                "and [[5, 6], [7, 8]]."
            ),
            "conversation": [],
        },
    )

    assert result["iterations"] == 2
    assert result["stop_reason"] == "FINAL_RESPONSE"
    assert result["provider_id"] == "deterministic"
    assert result["provider_version"] == "1.0.0"
    assert result["model"] == "deterministic-v1"
    assert result["response_text"] == (
        "The matrix product is [[19, 22], [43, 50]]."
    )

def test_message_executes_complex_math_through_production_path(
    tmp_path,
    monkeypatch,
):
    repository_root = Path(__file__).resolve().parents[3]

    request_id = str(uuid4())
    task_id = str(uuid4())

    def complex_math_responder(model_request):
        if len(model_request.messages) == 1:
            return json.dumps(
                {
                    "contract_version": "1.0",
                    "decision_type": "TOOL_PROPOSAL",
                    "response_text": None,
                    "tool_call": {
                        "request_id": request_id,
                        "task_id": task_id,
                        "tool": "anne.complex_math",
                        "operation": "run",
                        "arguments": {
                            "operation": "multiply",
                            "left": {
                                "real": 1,
                                "imaginary": 2,
                            },
                            "right": {
                                "real": 3,
                                "imaginary": 4,
                            },
                        },
                    },
                }
            )

        assert len(model_request.messages) == 3

        tool_message = model_request.messages[2]

        assert tool_message.role.value == "tool"
        assert tool_message.name == "anne.complex_math"
        assert '"real": -5.0' in tool_message.content
        assert '"imaginary": 10.0' in tool_message.content

        return json.dumps(
            {
                "contract_version": "1.0",
                "decision_type": "FINAL_RESPONSE",
                "response_text": (
                    "The complex multiplication result is "
                    "-5 + 10i."
                ),
                "tool_call": None,
            }
        )

    monkeypatch.setattr(
        RuntimeApplication,
        "_deterministic_responder",
        staticmethod(complex_math_responder),
    )

    application = RuntimeApplication(
        repository_root=repository_root,
    )

    result = application.handle_message(
        request_id=request_id,
        task_id=task_id,
        payload={
            "user_intent": (
                "Multiply (1 + 2i) by (3 + 4i)."
            ),
            "conversation": [],
        },
    )

    assert result["iterations"] == 2
    assert result["stop_reason"] == "FINAL_RESPONSE"
    assert result["provider_id"] == "deterministic"
    assert result["provider_version"] == "1.0.0"
    assert result["model"] == "deterministic-v1"
    assert result["response_text"] == (
        "The complex multiplication result is -5 + 10i."
    )

def test_message_executes_differential_equations_through_production_path(
    tmp_path,
    monkeypatch,
):
    repository_root = Path(__file__).resolve().parents[3]

    request_id = str(uuid4())
    task_id = str(uuid4())

    def differential_equations_responder(model_request):
        if len(model_request.messages) == 1:
            return json.dumps(
                {
                    "contract_version": "1.0",
                    "decision_type": "TOOL_PROPOSAL",
                    "response_text": None,
                    "tool_call": {
                        "request_id": request_id,
                        "task_id": task_id,
                        "tool": "anne.differential_equations",
                        "operation": "run",
                        "arguments": {
                            "operation": "rk4",
                            "expression": "y",
                            "t0": 0.0,
                            "y0": 1.0,
                            "tf": 1.0,
                            "step_size": 0.1,
                        },
                    },
                }
            )

        assert len(model_request.messages) == 3

        tool_message = model_request.messages[2]

        assert tool_message.role.value == "tool"
        assert tool_message.name == "anne.differential_equations"
        assert '"operation": "rk4"' in tool_message.content
        assert '"steps": 10' in tool_message.content
        assert '"t": 1.0' in tool_message.content
        assert '"y":' in tool_message.content

        return json.dumps(
            {
                "contract_version": "1.0",
                "decision_type": "FINAL_RESPONSE",
                "response_text": (
                    "The RK4 solution of dy/dt = y with "
                    "y(0) = 1 over 0 to 1 is approximately 2.71828."
                ),
                "tool_call": None,
            }
        )

    monkeypatch.setattr(
        RuntimeApplication,
        "_deterministic_responder",
        staticmethod(differential_equations_responder),
    )

    application = RuntimeApplication(
        repository_root=repository_root,
    )

    result = application.handle_message(
        request_id=request_id,
        task_id=task_id,
        payload={
            "user_intent": (
                "Solve dy/dt = y with y(0) = 1 "
                "from t=0 to t=1 using RK4."
            ),
            "conversation": [],
        },
    )

    assert result["iterations"] == 2
    assert result["stop_reason"] == "FINAL_RESPONSE"
    assert result["provider_id"] == "deterministic"
    assert result["provider_version"] == "1.0.0"
    assert result["model"] == "deterministic-v1"
    assert (
        result["response_text"]
        == (
            "The RK4 solution of dy/dt = y with "
            "y(0) = 1 over 0 to 1 is approximately 2.71828."
        )
    )

def test_message_executes_probability_through_production_path(
    tmp_path,
    monkeypatch,
):
    repository_root = Path(__file__).resolve().parents[3]

    request_id = str(uuid4())
    task_id = str(uuid4())

    def probability_responder(model_request):
        if len(model_request.messages) == 1:
            return json.dumps(
                {
                    "contract_version": "1.0",
                    "decision_type": "TOOL_PROPOSAL",
                    "response_text": None,
                    "tool_call": {
                        "request_id": request_id,
                        "task_id": task_id,
                        "tool": "anne.probability",
                        "operation": "run",
                        "arguments": {
                            "operation": "binomial",
                            "n": 5,
                            "k": 2,
                            "p": 0.5,
                        },
                    },
                }
            )

        tool_message = model_request.messages[-1]
        assert tool_message.role.value == "tool"
        assert tool_message.name == "anne.probability"
        assert '"operation": "binomial"' in tool_message.content
        assert '"result": 0.3125' in tool_message.content

        return json.dumps(
            {
                "contract_version": "1.0",
                "decision_type": "FINAL_RESPONSE",
                "response_text": "The binomial probability is 0.3125.",
                "tool_call": None,
            }
        )

    monkeypatch.setattr(
        RuntimeApplication,
        "_deterministic_responder",
        staticmethod(probability_responder),
    )

    application = RuntimeApplication(
        repository_root=repository_root,
    )

    result = application.handle_message(
        request_id=request_id,
        task_id=task_id,
        payload={
            "user_intent": (
                "Calculate the binomial probability for "
                "n=5, k=2, p=0.5."
            ),
            "conversation": [],
        },
    )

    assert result["response_text"] == "The binomial probability is 0.3125."
    assert result["stop_reason"] == "FINAL_RESPONSE"


def test_message_executes_statistics_through_production_path(
    tmp_path,
    monkeypatch,
):
    repository_root = Path(__file__).resolve().parents[3]

    request_id = str(uuid4())
    task_id = str(uuid4())

    def statistics_responder(model_request):
        if len(model_request.messages) == 1:
            return json.dumps(
                {
                    "contract_version": "1.0",
                    "decision_type": "TOOL_PROPOSAL",
                    "response_text": None,
                    "tool_call": {
                        "request_id": request_id,
                        "task_id": task_id,
                        "tool": "anne.statistics",
                        "operation": "run",
                        "arguments": {
                            "operation": "mean",
                            "values": [1, 2, 3, 4],
                        },
                    },
                }
            )

        assert len(model_request.messages) == 3

        tool_message = model_request.messages[2]

        assert tool_message.role.value == "tool"
        assert tool_message.name == "anne.statistics"
        assert '"operation": "mean"' in tool_message.content
        assert '"result": 2.5' in tool_message.content

        return json.dumps(
            {
                "contract_version": "1.0",
                "decision_type": "FINAL_RESPONSE",
                "response_text": (
                    "The mean of the dataset [1, 2, 3, 4] is 2.5."
                ),
                "tool_call": None,
            }
        )

    monkeypatch.setattr(
        RuntimeApplication,
        "_deterministic_responder",
        staticmethod(statistics_responder),
    )

    application = RuntimeApplication(
        repository_root=repository_root,
    )

    result = application.handle_message(
        request_id=request_id,
        task_id=task_id,
        payload={
            "user_intent": (
                "Calculate the mean of [1, 2, 3, 4]."
            ),
            "conversation": [],
        },
    )

    assert result["iterations"] == 2
    assert result["stop_reason"] == "FINAL_RESPONSE"
    assert result["provider_id"] == "deterministic"
    assert result["provider_version"] == "1.0.0"
    assert result["model"] == "deterministic-v1"
    assert result["response_text"] == (
        "The mean of the dataset [1, 2, 3, 4] is 2.5."
    )
from pathlib import Path
from uuid import uuid4
import json


def test_message_executes_interpolation_through_production_path(
    tmp_path,
    monkeypatch,
):
    repository_root = Path(__file__).resolve().parents[3]

    request_id = str(uuid4())
    task_id = str(uuid4())

    def interpolation_responder(model_request):
        if len(model_request.messages) == 1:
            return json.dumps(
                {
                    "contract_version": "1.0",
                    "decision_type": "TOOL_PROPOSAL",
                    "response_text": None,
                    "tool_call": {
                        "request_id": request_id,
                        "task_id": task_id,
                        "tool": "anne.interpolation",
                        "operation": "run",
                        "arguments": {
                            "operation": "linear",
                            "x_values": [0.0, 10.0],
                            "y_values": [0.0, 20.0],
                            "x": 2.5,
                        },
                    },
                }
            )

        tool_message = model_request.messages[-1]

        assert tool_message.role.value == "tool"
        assert tool_message.name == "anne.interpolation"
        assert '"operation": "linear"' in tool_message.content
        assert '"result": 5.0' in tool_message.content

        return json.dumps(
            {
                "contract_version": "1.0",
                "decision_type": "FINAL_RESPONSE",
                "response_text": (
                    "Linear interpolation gives a value of 5.0."
                ),
                "tool_call": None,
            }
        )

    monkeypatch.setattr(
        RuntimeApplication,
        "_deterministic_responder",
        staticmethod(interpolation_responder),
    )

    application = RuntimeApplication(
        repository_root=repository_root,
    )

    result = application.handle_message(
        request_id=request_id,
        task_id=task_id,
        payload={
            "user_intent": (
                "Linearly interpolate the engineering data "
                "at x=2.5."
            ),
            "conversation": [],
        },
    )

    assert result["response_text"] == (
        "Linear interpolation gives a value of 5.0."
    )
    assert result["stop_reason"] == "FINAL_RESPONSE"
def test_message_executes_regression_through_production_path(
    monkeypatch,
):
    repository_root = Path(__file__).resolve().parents[3]

    request_id = str(uuid4())
    task_id = str(uuid4())

    def regression_responder(model_request):
        if len(model_request.messages) == 1:
            return json.dumps(
                {
                    "contract_version": "1.0",
                    "decision_type": "TOOL_PROPOSAL",
                    "response_text": None,
                    "tool_call": {
                        "request_id": request_id,
                        "task_id": task_id,
                        "tool": "anne.regression",
                        "operation": "run",
                        "arguments": {
                            "operation": "linear",
                            "x_values": [1.0, 2.0, 3.0, 4.0],
                            "y_values": [3.0, 5.0, 7.0, 9.0],
                        },
                    },
                }
            )

        tool_message = model_request.messages[-1]

        assert tool_message.role.value == "tool"
        assert tool_message.name == "anne.regression"
        assert '"operation": "linear"' in tool_message.content
        assert '"slope": 2.0' in tool_message.content

        return json.dumps(
            {
                "contract_version": "1.0",
                "decision_type": "FINAL_RESPONSE",
                "response_text": (
                    "The regression line has a slope of 2.0."
                ),
                "tool_call": None,
            }
        )

    monkeypatch.setattr(
        RuntimeApplication,
        "_deterministic_responder",
        staticmethod(regression_responder),
    )

    application = RuntimeApplication(
        repository_root=repository_root,
    )

    result = application.handle_message(
        request_id=request_id,
        task_id=task_id,
        payload={
            "user_intent": (
                "Perform a linear regression on the engineering data."
            ),
            "conversation": [],
        },
    )

    assert result["response_text"] == (
        "The regression line has a slope of 2.0."
    )
    assert result["stop_reason"] == "FINAL_RESPONSE"


def test_runtime_application_executes_numerical_methods(
    monkeypatch,
):
    """Numerical methods must execute through the production runtime path."""
    from pathlib import Path

    repository_root = Path(__file__).resolve().parents[3]

    def numerical_methods_responder(model_request):
        if len(model_request.messages) == 1:
            return json.dumps(
                {
                    "contract_version": "1.0",
                    "decision_type": "TOOL_PROPOSAL",
                    "response_text": None,
                    "tool_call": {
                        "request_id": "00000000-0000-0000-0000-000000000101",
                        "task_id": "00000000-0000-0000-0000-000000000102",
                        "tool": "anne.numerical_methods",
                        "operation": "run",
                        "arguments": {
                            "operation": "bisection",
                            "expression": "x**2 - 2",
                            "lower": 1.0,
                            "upper": 2.0,
                            "tolerance": 1e-6,
                            "max_iterations": 100,
                        },
                    },
                }
            )

        assert len(model_request.messages) == 3
        tool_message = model_request.messages[2]

        assert tool_message.role.value == "tool"
        assert tool_message.name == "anne.numerical_methods"
        assert '"operation": "bisection"' in tool_message.content
        assert '"converged": true' in tool_message.content

        return json.dumps(
            {
                "contract_version": "1.0",
                "decision_type": "FINAL_RESPONSE",
                "response_text": "The root is approximately 1.41421356.",
                "tool_call": None,
            }
        )

    monkeypatch.setattr(
        RuntimeApplication,
        "_deterministic_responder",
        staticmethod(numerical_methods_responder),
    )

    application = RuntimeApplication(
        repository_root=repository_root,
    )

    result = application.handle_message(
        request_id="00000000-0000-0000-0000-000000000101",
        task_id="00000000-0000-0000-0000-000000000102",
        payload={
            "user_intent": "Find the square root of 2 using bisection.",
            "conversation": [],
        },
    )

    assert result["stop_reason"] == "FINAL_RESPONSE"
    assert "1.41421356" in result["response_text"]

def test_runtime_application_executes_signal_processing(monkeypatch):
    request_id = "00000000-0000-0000-0000-000000000003"
    task_id = "00000000-0000-0000-0000-000000000004"

    def signal_processing_responder(model_request):
        if len(model_request.messages) == 1:
            return json.dumps(
                {
                    "contract_version": "1.0",
                    "decision_type": "TOOL_PROPOSAL",
                    "response_text": None,
                    "tool_call": {
                        "request_id": request_id,
                        "task_id": task_id,
                        "tool": "anne.signal_processing",
                        "operation": "run",
                        "arguments": {
                            "operation": "rms",
                            "values": [3.0, 4.0],
                        },
                    },
                }
            )

        assert len(model_request.messages) == 3

        tool_message = model_request.messages[2]

        assert tool_message.role.value == "tool"
        assert tool_message.name == "anne.signal_processing"
        assert '"operation": "rms"' in tool_message.content
        assert '"result": 3.5355339059327378' in tool_message.content

        return json.dumps(
            {
                "contract_version": "1.0",
                "decision_type": "FINAL_RESPONSE",
                "response_text": "The RMS value is approximately 3.5355.",
                "tool_call": None,
            }
        )

    monkeypatch.setattr(
        RuntimeApplication,
        "_deterministic_responder",
        staticmethod(signal_processing_responder),
    )

    application = RuntimeApplication(
        repository_root=Path(__file__).resolve().parents[3]
    )

    result = application.handle_message(
        request_id=request_id,
        task_id=task_id,
        payload={
            "user_intent": "Calculate the RMS of the signal [3, 4].",
            "conversation": [],
        },
    )

    assert result["iterations"] == 2
    assert result["stop_reason"] == "FINAL_RESPONSE"
    assert result["provider_id"] == "deterministic"
    assert result["provider_version"] == "1.0.0"
    assert result["model"] == "deterministic-v1"
    assert result["response_text"] == (
        "The RMS value is approximately 3.5355."
    )


def test_runtime_application_executes_circuit_analysis_tool_production_path(
    monkeypatch,
):
    request_id = "00000000-0000-0000-0000-000000000007"
    task_id = "00000000-0000-0000-0000-000000000008"

    def circuit_analysis_responder(model_request):
        if len(model_request.messages) == 1:
            return json.dumps(
                {
                    "contract_version": "1.0",
                    "decision_type": "TOOL_PROPOSAL",
                    "response_text": None,
                    "tool_call": {
                        "request_id": request_id,
                        "task_id": task_id,
                        "tool": "anne.circuit_analysis",
                        "operation": "run",
                        "arguments": {
                            "operation": "ohms_law",
                            "voltage": 12.0,
                            "resistance": 4.0,
                        },
                    },
                }
            )

        assert len(model_request.messages) == 3

        tool_message = model_request.messages[2]

        assert tool_message.role.value == "tool"
        assert tool_message.name == "anne.circuit_analysis"
        assert '"operation": "ohms_law"' in tool_message.content
        assert '"current": 3.0' in tool_message.content

        return json.dumps(
            {
                "contract_version": "1.0",
                "decision_type": "FINAL_RESPONSE",
                "response_text": (
                    "Ohm's law calculated the current successfully."
                ),
                "tool_call": None,
            }
        )

    monkeypatch.setattr(
        RuntimeApplication,
        "_deterministic_responder",
        staticmethod(circuit_analysis_responder),
    )

    application = RuntimeApplication(
        repository_root=Path(__file__).resolve().parents[3]
    )

    result = application.handle_message(
        request_id=request_id,
        task_id=task_id,
        payload={
            "user_intent": (
                "Calculate the current through a 4 ohm resistor at 12 volts."
            ),
            "conversation": [],
        },
    )

    assert result["iterations"] == 2
    assert result["stop_reason"] == "FINAL_RESPONSE"
    assert result["provider_id"] == "deterministic"
    assert result["provider_version"] == "1.0.0"
    assert result["model"] == "deterministic-v1"
    assert result["response_text"] == (
        "Ohm's law calculated the current successfully."
    )


def test_runtime_application_executes_frequency_domain_signal_processing(monkeypatch):
    request_id = "00000000-0000-0000-0000-000000000005"
    task_id = "00000000-0000-0000-0000-000000000006"

    def frequency_domain_responder(model_request):
        if len(model_request.messages) == 1:
            return json.dumps(
                {
                    "contract_version": "1.0",
                    "decision_type": "TOOL_PROPOSAL",
                    "response_text": None,
                    "tool_call": {
                        "request_id": request_id,
                        "task_id": task_id,
                        "tool": "anne.signal_processing.frequency_domain",
                        "operation": "run",
                        "arguments": {
                            "operation": "fft",
                            "values": [1.0, 0.0, 0.0, 0.0],
                        },
                    },
                }
            )

        assert len(model_request.messages) == 3

        tool_message = model_request.messages[2]

        assert tool_message.role.value == "tool"
        assert tool_message.name == "anne.signal_processing.frequency_domain"
        assert '"operation": "fft"' in tool_message.content
        assert '"real": 1.0' in tool_message.content

        return json.dumps(
            {
                "contract_version": "1.0",
                "decision_type": "FINAL_RESPONSE",
                "response_text": "The FFT was calculated successfully.",
                "tool_call": None,
            }
        )

    monkeypatch.setattr(
        RuntimeApplication,
        "_deterministic_responder",
        staticmethod(frequency_domain_responder),
    )

    application = RuntimeApplication(
        repository_root=Path(__file__).resolve().parents[3]
    )

    result = application.handle_message(
        request_id=request_id,
        task_id=task_id,
        payload={
            "user_intent": "Calculate the FFT of [1, 0, 0, 0].",
            "conversation": [],
        },
    )

    assert result["iterations"] == 2
    assert result["stop_reason"] == "FINAL_RESPONSE"
    assert result["provider_id"] == "deterministic"
    assert result["provider_version"] == "1.0.0"
    assert result["model"] == "deterministic-v1"
    assert result["response_text"] == "The FFT was calculated successfully."
