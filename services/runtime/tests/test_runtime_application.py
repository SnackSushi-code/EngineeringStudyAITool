from __future__ import annotations

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