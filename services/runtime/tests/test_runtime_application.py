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
