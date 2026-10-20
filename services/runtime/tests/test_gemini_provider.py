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
    assert "response_json_schema" not in call["config"]


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



def test_provider_includes_engineering_candidates_in_runtime_context():
    provider = GeminiModelProvider(
        api_key="test-key",
        model=MODEL,
        client=FakeClient(response=make_response()),
    )

    request = make_request()
    request = ModelRequest(
        request_id=request.request_id,
        task_id=request.task_id,
        messages=request.messages,
        model=request.model,
        generation=request.generation,
        metadata={
            "anne.engineering_candidates": (
                '[{"tool_id":"anne.thermodynamics",'
                '"engineering_domain":"thermodynamics",'
                '"description":"Thermodynamics calculations"}]'
            )
        },
    )

    provider.generate(request)

    call = provider._client.models.calls[0]
    contents = call["contents"]

    user_text = contents[0]["parts"][0]["text"]

    assert "Ann-E engineering capability candidates:" in user_text
    assert "anne.thermodynamics" in user_text
    assert "thermodynamics" in user_text
    assert "Thermodynamics calculations" in user_text


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


def test_provider_maps_server_error_code_to_retryable_server_error():
    class FakeServerError(Exception):
        code = 503

    provider = GeminiModelProvider(
        api_key="test-key",
        model=MODEL,
        client=FakeClient(
            error=FakeServerError(
                "503 UNAVAILABLE: model is currently experiencing high demand"
            ),
        ),
    )

    with pytest.raises(
        ModelProviderError,
        match="server error",
    ) as exc_info:
        provider.generate(make_request())

    assert exc_info.value.code == "GEMINI_SERVER_ERROR"
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

    assert call["config"]["response_mime_type"] == "application/json"
    assert "response_json_schema" not in call["config"]

def test_provider_maps_google_client_error_to_invalid_request():
    from google.genai.errors import ClientError

    error = ClientError(
        400,
        {
            "error": {
                "status": "INVALID_ARGUMENT",
                "message": "sensitive request details must not be exposed",
            }
        },
        None,
    )
    provider = GeminiModelProvider(
        api_key="test-key",
        model=MODEL,
        client=FakeClient(error=error),
    )

    with pytest.raises(ModelProviderError) as exc_info:
        provider.generate(make_request())

    assert exc_info.value.code == "GEMINI_INVALID_REQUEST"
    assert exc_info.value.retryable is False
    assert "HTTP 400" in str(exc_info.value)
    assert "INVALID_ARGUMENT" in str(exc_info.value)
    assert "sensitive request details" not in str(exc_info.value)


def test_provider_maps_google_client_error_rate_limit():
    from google.genai.errors import ClientError

    error = ClientError(
        429,
        {"error": {"status": "RESOURCE_EXHAUSTED", "message": "rate limited"}},
        None,
    )
    provider = GeminiModelProvider(
        api_key="test-key",
        model=MODEL,
        client=FakeClient(error=error),
    )

    with pytest.raises(ModelProviderError) as exc_info:
        provider.generate(make_request())

    assert exc_info.value.code == "GEMINI_RATE_LIMITED"
    assert exc_info.value.retryable is True
    assert "HTTP 429" in str(exc_info.value)


def test_provider_maps_google_client_error_server_failure():
    from google.genai.errors import ServerError

    error = ServerError(
        503,
        {"error": {"status": "UNAVAILABLE", "message": "temporary failure"}},
        None,
    )
    provider = GeminiModelProvider(
        api_key="test-key",
        model=MODEL,
        client=FakeClient(error=error),
    )

    with pytest.raises(ModelProviderError) as exc_info:
        provider.generate(make_request())

    assert exc_info.value.code == "GEMINI_SERVER_ERROR"
    assert exc_info.value.retryable is True
    assert "HTTP 503" in str(exc_info.value)


def test_provider_maps_google_client_error_not_found():
    from google.genai.errors import ClientError

    error = ClientError(
        404,
        {"error": {"status": "NOT_FOUND", "message": "resource not found"}},
        None,
    )
    provider = GeminiModelProvider(
        api_key="test-key",
        model=MODEL,
        client=FakeClient(error=error),
    )

    with pytest.raises(ModelProviderError) as exc_info:
        provider.generate(make_request())

    assert exc_info.value.code == "GEMINI_RESOURCE_NOT_FOUND"
    assert exc_info.value.retryable is False
    assert "HTTP 404" in str(exc_info.value)

def test_provider_rejects_truncated_json_as_length_error():
    provider = GeminiModelProvider(
        api_key="test-key",
        model=MODEL,
    )

    response = SimpleNamespace(
        parsed=None,
        text='{"contract_version":"1.0","decision_type":"FINAL_RESPONSE"',
        candidates=[
            SimpleNamespace(
                finish_reason="MAX_TOKENS",
            ),
        ],
    )

    provider._client = FakeClient(response=response)

    with pytest.raises(
        ModelProviderError,
        match="truncated",
    ) as exc_info:
        provider.generate(make_request())

    assert exc_info.value.code == "GEMINI_OUTPUT_TRUNCATED"
    assert exc_info.value.retryable is True

def test_final_response_formatter_boxes_final_equation_and_removes_duplicate():
    text = (
        "Use the kinematic equation first.\n"
        "$v = 0 + (3)(5)$\n"
        "$v = 15\\ \\text{m/s}$\n"
        "$v = 15\\ \\text{m/s}$"
    )

    result = GeminiModelProvider._format_final_response(text)

    assert result.count(r"\boxed{") == 1
    assert result.count("v = 15") == 1
    assert r"\text{m/s}" in result
    assert "Use the kinematic equation first." in result
    assert "$v = 0 + (3)(5)$" in result

def test_final_response_formatter_does_not_double_box_existing_answer():
    text = "Calculation complete.\n$$\n\\boxed{v = 15\\ \\text{m/s}}\n$$"

    result = GeminiModelProvider._format_final_response(text)

    assert result.count(r"\boxed{") == 1
    assert "Calculation complete." in result

def test_final_response_formatter_removes_repeated_multiline_final_equation():
    text = (
        "Calculation:\n\n"
        "$$\nv = 0 + (3)(5)\n$$\n\n"
        "The final velocity is:\n\n"
        "$$\nv = 15\\ \\text{m/s}\n$$\n\n"
        "$$\nv = 15\\ \\text{m/s}\n$$"
    )

    result = GeminiModelProvider._format_final_response(text)

    assert result.count(r"\boxed{") == 1
    assert result.count("v = 15") == 1
    assert r"\text{m/s}" in result
    assert "v = 0 + (3)(5)" in result
    assert "The final velocity is:" in result

def test_final_response_formatter_preserves_prose_containing_equals():
    text = "Ohm's law is V = I ? R."

    result = GeminiModelProvider._format_final_response(text)

    assert result == text

def test_final_response_formatter_boxes_final_inline_equation():
    text = "Substitution gives $v = 15\\ \\text{m/s}$"

    result = GeminiModelProvider._format_final_response(text)

    assert result.count(r"\boxed{") == 1
    assert result.count("v = 15") == 1
    assert r"\text{m/s}" in result

def test_final_response_formatter_starts_display_math_on_new_line():
    text = "Solving gives $x = 5$.\n\nFinal answer: $x = 5$"

    result = GeminiModelProvider._format_final_response(text)

    assert "Final answer:\n\n$$\n\\boxed{x = 5}\n$$" in result
    assert result.count(r"\boxed{") == 1

def test_system_instruction_explains_safe_tool_selection():
    instruction = GeminiModelProvider.SYSTEM_INSTRUCTION

    assert "available tool catalog" in instruction
    assert "declared capabilities" in instruction
    assert "argument schema" in instruction

def test_system_instruction_requires_markdown_math_formatting():
    instruction = GeminiModelProvider.SYSTEM_INSTRUCTION

    assert "display equations" in instruction
    assert "final numerical or symbolic answer exactly once" in instruction
    assert "Do not repeat the same final result" in instruction
    assert "Make the final answer visually distinct" in instruction
    assert "display-math block" in instruction
    assert r"\boxed{...}" in instruction
    assert "Never put an entire response inside one math block" in instruction
    assert "instead of inventing a tool or operation" in instruction
    assert "does not mean the tool has run" in instruction
    assert "Never fabricate tool output" in instruction
    assert "runtime security boundaries" in instruction

def test_final_inline_answer_after_earlier_display_equation():
    text = (
        "First calculate:\n\n"
        "$$\nv = u + at\n$$\n\n"
        "Final answer: $v = 15$"
    )

    result = GeminiModelProvider._format_final_response(text)

    assert r"\boxed{v = 15}" in result
    assert "$$\nv = u + at\n$$" in result
    assert result.count(r"\boxed{") == 1

def test_final_display_equation_with_terminal_punctuation():
    text = "Final answer: $$\nx = 5.\n$$"

    result = GeminiModelProvider._format_final_response(text)

    assert "$$\n\\boxed{x = 5}\n$$." in result
    assert result.count(r"\boxed{") == 1

def test_final_display_answer_deduplicates_result_after_explanation():
    text = (
        "Evaluating the expression:\n\n"
        "$$\nv_f = 15\\ \\text{m/s}\n$$\n\n"
        "Final answer:\n\n"
        "$$\nv_f = 15\\ \\text{m/s}\n$$"
    )

    result = GeminiModelProvider._format_final_response(text)

    assert result.count("v_f = 15") == 1
    assert result.count(r"\boxed{") == 1
    assert "Evaluating the expression:" in result
    assert "Final answer:" in result
    assert r"\text{m/s}" in result

def test_final_boxed_display_answer_deduplicates_previous_result():
    text = (
        "Substituting the given values:\n\n"
        "$$\nv_f = 0\\ \\text{m/s} + (3\\ \\text{m/s}^2)(5\\ \\text{s})\n$$\n\n"
        "Evaluating the expression:\n\n"
        "$$\nv_f = 15\\ \\text{m/s}\n$$\n\n"
        "$$\n\\boxed{v_f = 15\\ \\text{m/s}}\n$$"
    )

    result = GeminiModelProvider._format_final_response(text)

    assert result.count("v_f = 15") == 1
    assert result.count(r"\boxed{") == 1
    assert "Substituting the given values:" in result
    assert "Evaluating the expression:" in result
    assert "v_f = 0" in result
    assert r"\text{m/s}" in result

def test_normalize_model_decision_preserves_latex_backslashes_from_structured_json():
    raw_content = r'''{
      "contract_version": "1.0",
      "decision_type": "FINAL_RESPONSE",
      "response_text": "$$ V = I \\times R $$\n\n$$ V = 15 \\ \\text{V} $$\n\n$$ \\boxed{V = 15 \\ \\text{V}} $$",
      "tool_call": null
    }'''

    result = GeminiModelProvider._normalize_model_decision(
        raw_content,
        make_request(),
    )

    payload = json.loads(result)

    assert r"\times" in payload["response_text"]
    assert r"\text{V}" in payload["response_text"]
    assert r"\boxed{" in payload["response_text"]

def test_provider_system_instruction_requires_tool_when_explicitly_requested():
    instruction = GeminiModelProvider.SYSTEM_INSTRUCTION

    assert (
        "If the user explicitly requests a registered tool" in instruction
    )
    assert (
        "MUST return TOOL_PROPOSAL" in instruction
    )
    assert (
        "do not calculate the answer yourself" in instruction
    )

def test_provider_descriptor_advertises_tool_calling_capability():
    """Gemini must advertise tool calling for production tool routing."""
    from anne_runtime.model_contracts import ModelCapability

    provider = GeminiModelProvider()

    assert ModelCapability.TOOL_CALLING in provider.descriptor.capabilities
