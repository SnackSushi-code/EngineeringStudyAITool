from __future__ import annotations

import pytest

from anne_runtime.model_contracts import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelRole,
)
from anne_runtime.model_provider_factory import (
    DETERMINISTIC_MODEL,
    DETERMINISTIC_PROVIDER_ID,
    GEMINI_MODEL,
    GEMINI_PROVIDER_ID,
    ModelProviderConfigurationError,
    ModelProviderFactory,
)


def deterministic_responder(request):
    return "deterministic response"


def make_request(request_id: str, task_id: str) -> ModelRequest:
    return ModelRequest(
        request_id=request_id,
        task_id=task_id,
        messages=(
            ModelMessage(
                role=ModelRole.USER,
                content="hello",
            ),
        ),
    )


def fake_gemini_response(
    self,
    request: ModelRequest,
) -> ModelResponse:
    return ModelResponse(
        request_id=request.request_id,
        task_id=request.task_id,
        provider_id=GEMINI_PROVIDER_ID,
        provider_version="1.0.0",
        model=request.model,
        content="gemini test response",
        finish_reason="stop",
    )


def test_factory_defaults_to_deterministic(monkeypatch):
    monkeypatch.delenv("ANNE_MODEL_PROVIDER", raising=False)
    monkeypatch.delenv("ANNE_MODEL_NAME", raising=False)
    monkeypatch.delenv("ANNE_GEMINI_MODEL", raising=False)

    service = ModelProviderFactory(
        deterministic_responder=deterministic_responder,
    ).build_model_service()

    invocation = service.invoke(
        make_request(
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000002",
        )
    )

    assert invocation.response.provider_id == DETERMINISTIC_PROVIDER_ID
    assert invocation.response.model == DETERMINISTIC_MODEL
    assert invocation.response.content == "deterministic response"


def test_factory_selects_gemini(monkeypatch):
    monkeypatch.setenv("ANNE_MODEL_PROVIDER", GEMINI_PROVIDER_ID)
    monkeypatch.setenv("ANNE_MODEL_NAME", GEMINI_MODEL)

    monkeypatch.setattr(
        "anne_runtime.gemini_provider.GeminiModelProvider.generate",
        fake_gemini_response,
    )

    service = ModelProviderFactory(
        deterministic_responder=deterministic_responder,
    ).build_model_service()

    invocation = service.invoke(
        make_request(
            "00000000-0000-0000-0000-000000000003",
            "00000000-0000-0000-0000-000000000004",
        )
    )

    assert invocation.response.provider_id == GEMINI_PROVIDER_ID
    assert invocation.response.model == GEMINI_MODEL
    assert invocation.response.content == "gemini test response"


def test_factory_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("ANNE_MODEL_PROVIDER", "unknown-provider")

    with pytest.raises(
        ModelProviderConfigurationError,
        match="Unsupported model provider",
    ):
        ModelProviderFactory(
            deterministic_responder=deterministic_responder,
        ).build_model_service()


def test_factory_rejects_unsupported_deterministic_model(monkeypatch):
    monkeypatch.setenv("ANNE_MODEL_PROVIDER", DETERMINISTIC_PROVIDER_ID)
    monkeypatch.setenv("ANNE_MODEL_NAME", "unsupported-model")

    with pytest.raises(
        ModelProviderConfigurationError,
        match="Unsupported deterministic model",
    ):
        ModelProviderFactory(
            deterministic_responder=deterministic_responder,
        ).build_model_service()


def test_factory_honors_gemini_specific_model(monkeypatch):
    monkeypatch.setenv("ANNE_MODEL_PROVIDER", GEMINI_PROVIDER_ID)
    monkeypatch.delenv("ANNE_MODEL_NAME", raising=False)
    monkeypatch.setenv("ANNE_GEMINI_MODEL", "custom-gemini-model")

    monkeypatch.setattr(
        "anne_runtime.gemini_provider.GeminiModelProvider.generate",
        fake_gemini_response,
    )

    service = ModelProviderFactory(
        deterministic_responder=deterministic_responder,
    ).build_model_service()

    invocation = service.invoke(
        make_request(
            "00000000-0000-0000-0000-000000000005",
            "00000000-0000-0000-0000-000000000006",
        )
    )

    assert invocation.response.provider_id == GEMINI_PROVIDER_ID
    assert invocation.response.model == "custom-gemini-model"
    assert invocation.response.content == "gemini test response"

def test_factory_ignores_generic_model_name_for_gemini(monkeypatch):
    monkeypatch.setenv("ANNE_MODEL_PROVIDER", GEMINI_PROVIDER_ID)
    monkeypatch.setenv("ANNE_MODEL_NAME", "deterministic-v1")
    monkeypatch.setenv("ANNE_GEMINI_MODEL", "gemini-3.5-flash-lite")

    monkeypatch.setattr(
        "anne_runtime.gemini_provider.GeminiModelProvider.generate",
        fake_gemini_response,
    )

    service = ModelProviderFactory(
        deterministic_responder=deterministic_responder,
    ).build_model_service()

    invocation = service.invoke(
        make_request(
            "00000000-0000-0000-0000-000000000009",
            "00000000-0000-0000-0000-000000000010",
        )
    )

    assert invocation.response.provider_id == GEMINI_PROVIDER_ID
    assert invocation.response.model == "gemini-3.5-flash-lite"


def test_factory_rejects_blank_provider(monkeypatch):
    monkeypatch.setenv("ANNE_MODEL_PROVIDER", "   ")

    with pytest.raises(
        ModelProviderConfigurationError,
        match="Unsupported model provider",
    ):
        ModelProviderFactory(
            deterministic_responder=deterministic_responder,
        ).build_model_service()
