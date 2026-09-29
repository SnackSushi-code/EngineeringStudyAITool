from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from anne_runtime.gemini_provider import GeminiModelProvider
from anne_runtime.model_contracts import (
    ModelCapability,
    ModelContractError,
    ModelGenerationConfig,
    ModelMessage,
    ModelProviderError,
    ModelRequest,
    ModelRole,
)


MODEL = "gemini-3.5-flash-lite"


def make_request(
    *,
    content: str = "Explain Ohm's law.",
    model: str = MODEL,
) -> ModelRequest:
    return ModelRequest(
        request_id=str(uuid4()),
        task_id=str(uuid4()),
        messages=(
            ModelMessage(
                role=ModelRole.USER,
                content=content,
            ),
        ),
        model=model,
        required_capabilities=frozenset(
            {
                ModelCapability.TEXT_INPUT,
                ModelCapability.TEXT_OUTPUT,
                ModelCapability.STRUCTURED_OUTPUT,
            }
        ),
        generation=ModelGenerationConfig(),
    )


def make_response(
    *,
    decision_type: str = "FINAL_RESPONSE",
    response_text: str | None = "Ohm's law is V = I Ã— R.",
    tool_call: dict | None = None,
) -> SimpleNamespace:
    payload = {
        "contract_version": "1.0",
        "decision_type": decision_type,
        "response_text": response_text,
        "tool_call": tool_call,
    }

    return SimpleNamespace(
        parsed=SimpleNamespace(**payload),
        text=json.dumps(payload),
    )


class FakeModels:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)

        if self.error is not None:
            raise self.error

        return self.response


class FakeClient:
    def __init__(self, response=None, error=None):
        self.models = FakeModels(
            response=response,
            error=error,
        )


def test_provider_descriptor_exposes_expected_identity_and_model():
    provider = GeminiModelProvider(
        api_key="test-key",
        model=MODEL,
    )

    descriptor = provider.descriptor

    assert descriptor.provider_id == "gemini"
    assert descriptor.provider_version == "1.0.0"
    assert MODEL in descriptor.models


def test_provider_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANNE_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(ModelProviderError, match="API key"):
        GeminiModelProvider(model=MODEL)


def test_provider_accepts_explicit_api_key():
    provider = GeminiModelProvider(
        api_key="test-key",
        model=MODEL,
    )

    assert provider is not None


def test_provider_accepts_model_from_environment(monkeypatch):
    monkeypatch.setenv("ANNE_GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("ANNE_GEMINI_MODEL", MODEL)

    provider = GeminiModelProvider()

    assert MODEL in provider.descriptor.models


def test_provider_rejects_unsupported_request_model():
    provider = GeminiModelProvider(
        api_key="test-key",
        model=MODEL,
    )

    request = make_request(model="unsupported-gemini-model")

    with pytest.raises(
        ModelContractError,
        match="Unsupported Gemini model",
    ):
        provider.generate(request)


def test_provider_canonicalizes_final_response():
    response = make_response(
        decision_type="FINAL_RESPONSE",
        response_text="Ohm's law is V = I Ã— R.",
    )

    client = FakeClient(response=response)

    provider = GeminiModelProvider(
        api_key="test-key",
        model=MODEL,
        client=client,
    )

    result = provider.generate(make_request())

    payload = json.loads(result.content)

    assert payload == {
        "contract_version": "1.0",
        "decision_type": "FINAL_RESPONSE",
        "response_text": "Ohm's law is V = I Ã— R.",
        "tool_call": None,
    }

    assert result.provider_id == "gemini"
    assert result.provider_version == "1.0.0"
    assert result.model == MODEL
    assert result.finish_reason.value == "stop"

    assert len(client.models.calls) == 1

    call = client.models.calls[0]

    assert call["model"] == MODEL
    assert call["config"]["response_mime_type"] == "application/json"
    assert "response_json_schema" in call["config"]


def test_provider_builds_structured_tool_proposal():
    request = make_request()

    tool_call = {
        "request_id": request.request_id,
        "task_id": request.task_id,
        "tool": "calculator",
        "operation": "evaluate",
        "arguments_json": '{"expression":"2 + 2"}',
    }

    response = make_response(
        decision_type="TOOL_PROPOSAL",
        response_text=None,
        tool_call=tool_call,
    )

    client = FakeClient(response=response)

    provider = GeminiModelProvider(
        api_key="test-key",
        model=MODEL,
        client=client,
    )

    result = provider.generate(request)

    payload = json.loads(result.content)

    assert payload["contract_version"] == "1.0"
    assert payload["decision_type"] == "TOOL_PROPOSAL"
    assert payload["response_text"] is None

    canonical_tool_call = payload["tool_call"]

    assert canonical_tool_call["request_id"] == request.request_id
    assert canonical_tool_call["task_id"] == request.task_id
    assert canonical_tool_call["tool"] == "calculator"
    assert canonical_tool_call["operation"] == "evaluate"
    assert canonical_tool_call["arguments"] == {
        "expression": "2 + 2",
    }


def test_provider_rejects_tool_proposal_with_wrong_request_id():
    request = make_request()

    tool_call = {
        "request_id": str(uuid4()),
        "task_id": request.task_id,
        "tool": "calculator",
        "operation": "evaluate",
        "arguments_json": '{"expression":"2 + 2"}',
    }

    response = make_response(
        decision_type="TOOL_PROPOSAL",
        response_text=None,
        tool_call=tool_call,
    )

    provider = GeminiModelProvider(
        api_key="test-key",
        model=MODEL,
        client=FakeClient(response=response),
    )

    with pytest.raises(
        ModelProviderError,
        match="wrong request_id",
    ):
        provider.generate(request)


def test_provider_rejects_tool_proposal_with_wrong_task_id():
    request = make_request()

    tool_call = {
        "request_id": request.request_id,
        "task_id": str(uuid4()),
        "tool": "calculator",
        "operation": "evaluate",
        "arguments_json": '{"expression":"2 + 2"}',
    }

    response = make_response(
        decision_type="TOOL_PROPOSAL",
        response_text=None,
        tool_call=tool_call,
    )

    provider = GeminiModelProvider(
        api_key="test-key",
        model=MODEL,
        client=FakeClient(response=response),
    )

    with pytest.raises(
        ModelProviderError,
        match="wrong task_id",
    ):
        provider.generate(request)


def test_provider_rejects_malformed_arguments_json():
    request = make_request()

    tool_call = {
        "request_id": request.request_id,
        "task_id": request.task_id,
        "tool": "calculator",
        "operation": "evaluate",
        "arguments_json": "{not-valid-json",
    }

    response = make_response(
        decision_type="TOOL_PROPOSAL",
        response_text=None,
        tool_call=tool_call,
    )

    provider = GeminiModelProvider(
        api_key="test-key",
        model=MODEL,
        client=FakeClient(response=response),
    )

    with pytest.raises(
        ModelProviderError,
        match="invalid JSON in arguments_json",
    ):
        provider.generate(request)


def test_provider_rejects_non_object_tool_arguments():
    request = make_request()

    tool_call = {
        "request_id": request.request_id,
        "task_id": request.task_id,
        "tool": "calculator",
        "operation": "evaluate",
        "arguments_json": '["2 + 2"]',
    }

    response = make_response(
        decision_type="TOOL_PROPOSAL",
        response_text=None,
        tool_call=tool_call,
    )

    provider = GeminiModelProvider(
        api_key="test-key",
        model=MODEL,
        client=FakeClient(response=response),
    )

    with pytest.raises(
        ModelProviderError,
        match="tool arguments must decode to a JSON object",
    ):
        provider.generate(request)



def test_provider_uses_default_timeout():
    client = FakeClient(response=make_response())

    provider = GeminiModelProvider(
        api_key="test-key",
        model=MODEL,
        client=client,
    )

    provider.generate(make_request())

    call = client.models.calls[0]

    assert call["config"]["http_options"]["timeout"] == 120_000


def test_provider_uses_configured_timeout():
    client = FakeClient(response=make_response())

    provider = GeminiModelProvider(
        api_key="test-key",
        model=MODEL,
        client=client,
        timeout_ms=45_000,
    )

    provider.generate(make_request())

    call = client.models.calls[0]

    assert call["config"]["http_options"]["timeout"] == 45_000


def test_provider_reads_timeout_from_environment(monkeypatch):
    monkeypatch.setenv(
        "ANNE_GEMINI_TIMEOUT_MS",
        "30_000",
    )

    client = FakeClient(response=make_response())

    provider = GeminiModelProvider(
        api_key="test-key",
        model=MODEL,
        client=client,
    )

    provider.generate(make_request())

    call = client.models.calls[0]

    assert call["config"]["http_options"]["timeout"] == 30_000


def test_provider_rejects_invalid_timeout(monkeypatch):
    monkeypatch.setenv(
        "ANNE_GEMINI_TIMEOUT_MS",
        "not-an-integer",
    )

    with pytest.raises(
        ModelContractError,
        match="ANNE_GEMINI_TIMEOUT_MS must be an integer",
    ):
        GeminiModelProvider(
            api_key="test-key",
            model=MODEL,
            client=FakeClient(response=make_response()),
        )


def test_provider_rejects_non_positive_timeout():
    with pytest.raises(
        ModelContractError,
        match="timeout_ms must be greater than zero",
    ):
        GeminiModelProvider(
            api_key="test-key",
            model=MODEL,
            client=FakeClient(response=make_response()),
            timeout_ms=0,
        )


def test_provider_maps_timeout_to_retryable_transport_error():
    class FakeTimeoutError(Exception):
        pass

    provider = GeminiModelProvider(
        api_key="test-key",
        model=MODEL,
        client=FakeClient(
            error=FakeTimeoutError("request timed out"),
        ),
    )

    with pytest.raises(
        ModelProviderError,
        match="transport request failed",
    ) as exc_info:
        provider.generate(make_request())

    assert exc_info.value.code == "GEMINI_TRANSPORT_ERROR"
    assert exc_info.value.retryable is True


def test_provider_maps_api_failures_to_model_provider_error():
    class FakeUnauthorizedError(Exception):
        status_code = 401

    provider = GeminiModelProvider(
        api_key="test-key",
        model=MODEL,
        client=FakeClient(
            error=FakeUnauthorizedError("unauthorized"),
        ),
    )

    with pytest.raises(ModelProviderError, match="authentication"):
        provider.generate(make_request())


def test_provider_does_not_send_authority_fields_to_gemini():
    response = make_response()

    client = FakeClient(response=response)

    provider = GeminiModelProvider(
        api_key="test-key",
        model=MODEL,
        client=client,
    )

    provider.generate(make_request())

    call = client.models.calls[0]

    schema = call["config"]["response_json_schema"]

    serialized_schema = json.dumps(schema, default=str)

    forbidden_fields = (
        "permissions",
        "timeout_ms",
        "retry_mode",
        "idempotency_key",
        "schema_version",
    )

    for field in forbidden_fields:
        assert field not in serialized_schema
