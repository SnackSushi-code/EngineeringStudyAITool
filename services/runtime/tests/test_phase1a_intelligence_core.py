from __future__ import annotations

import pytest

from anne_runtime.deterministic_provider import (
    DeterministicModelProvider,
)
from anne_runtime.model_contracts import (
    ModelCapability,
    ModelContractError,
    ModelGenerationConfig,
    ModelMessage,
    ModelProviderError,
    ModelRequest,
    ModelRole,
)
from anne_runtime.model_router import ModelRouter
from anne_runtime.model_service import ModelService
from anne_runtime.provider_registry import ProviderRegistry


def make_request(
    *,
    model: str | None = None,
    capabilities: frozenset[ModelCapability] = frozenset(),
) -> ModelRequest:
    return ModelRequest(
        request_id="request-1",
        task_id="task-1",
        messages=(
            ModelMessage(
                role=ModelRole.USER,
                content="Hello Ann-E.",
            ),
        ),
        model=model,
        required_capabilities=capabilities,
        generation=ModelGenerationConfig(
            temperature=0.2,
            max_output_tokens=128,
        ),
    )


def test_model_request_serializes_without_secrets() -> None:
    request = make_request()

    payload = request.to_dict()

    assert payload["request_id"] == "request-1"
    assert payload["task_id"] == "task-1"
    assert payload["messages"][0]["role"] == "user"
    assert "api_key" not in str(payload).lower()


def test_model_generation_configuration_validates() -> None:
    with pytest.raises(ModelContractError):
        ModelGenerationConfig(temperature=3.0)

    with pytest.raises(ModelContractError):
        ModelGenerationConfig(max_output_tokens=0)

    with pytest.raises(ModelContractError):
        ModelGenerationConfig(top_p=0.0)


def test_registry_rejects_duplicate_provider() -> None:
    registry = ProviderRegistry()
    provider = DeterministicModelProvider()

    registry.register(provider)

    with pytest.raises(ModelContractError):
        registry.register(provider)


def test_registry_can_replace_provider_explicitly() -> None:
    registry = ProviderRegistry()

    first = DeterministicModelProvider(
        provider_id="test",
        provider_version="1",
    )

    second = DeterministicModelProvider(
        provider_id="test",
        provider_version="2",
    )

    registry.register(first)
    registry.register(second, replace=True)

    assert registry.get("test").descriptor.provider_version == "2"


def test_router_selects_requested_model() -> None:
    registry = ProviderRegistry()

    provider = DeterministicModelProvider(
        provider_id="test",
        models=("model-a", "model-b"),
    )

    registry.register(provider)

    router = ModelRouter(registry)

    route = router.resolve(
        make_request(model="model-b")
    )

    assert route.provider_id == "test"
    assert route.model == "model-b"


def test_router_respects_capability_requirements() -> None:
    registry = ProviderRegistry()

    provider = DeterministicModelProvider(
        provider_id="text-only",
        models=("text",),
    )

    registry.register(provider)

    router = ModelRouter(registry)

    route = router.resolve(
        make_request(
            capabilities=frozenset(
                {ModelCapability.TEXT_OUTPUT}
            )
        )
    )

    assert route.provider_id == "text-only"


def test_router_rejects_unsatisfied_capability() -> None:
    registry = ProviderRegistry()

    provider = DeterministicModelProvider()

    registry.register(provider)

    router = ModelRouter(registry)

    with pytest.raises(ModelProviderError) as exc_info:
        router.resolve(
            make_request(
                capabilities=frozenset(
                    {ModelCapability.VISION}
                )
            )
        )

    assert exc_info.value.code == "NO_ROUTE"


def test_router_rejects_empty_registry() -> None:
    router = ModelRouter(ProviderRegistry())

    with pytest.raises(ModelProviderError) as exc_info:
        router.resolve(make_request())

    assert exc_info.value.code == "NO_PROVIDERS"


def test_router_response_correlation_is_verified() -> None:
    class BadProvider(DeterministicModelProvider):
        def generate(self, request):
            response = super().generate(request)

            from dataclasses import replace

            return replace(
                response,
                request_id="wrong-request",
            )

    registry = ProviderRegistry()
    registry.register(BadProvider())

    router = ModelRouter(registry)

    with pytest.raises(ModelProviderError) as exc_info:
        router.generate(make_request())

    assert exc_info.value.code == "RESPONSE_CORRELATION_ERROR"


def test_model_service_returns_invocation_metadata() -> None:
    registry = ProviderRegistry()

    registry.register(
        DeterministicModelProvider(
            provider_id="deterministic",
            models=("deterministic-v1",),
        )
    )

    service = ModelService(
        ModelRouter(
            registry,
            default_provider_id="deterministic",
            default_model="deterministic-v1",
        )
    )

    invocation = service.invoke(make_request())

    assert invocation.route.provider_id == "deterministic"
    assert invocation.route.model == "deterministic-v1"
    assert invocation.response.request_id == "request-1"
    assert invocation.response.task_id == "task-1"
    assert invocation.duration_seconds >= 0


def test_model_service_enforces_input_limit() -> None:
    registry = ProviderRegistry()
    registry.register(DeterministicModelProvider())

    service = ModelService(
        ModelRouter(registry),
        max_input_characters=5,
    )

    with pytest.raises(ModelProviderError) as exc_info:
        service.invoke(
            ModelRequest(
                request_id="r",
                task_id="t",
                messages=(
                    ModelMessage(
                        role=ModelRole.USER,
                        content="123456",
                    ),
                ),
            )
        )

    assert exc_info.value.code == "INPUT_LIMIT_EXCEEDED"


def test_model_service_enforces_output_limit() -> None:
    registry = ProviderRegistry()

    registry.register(
        DeterministicModelProvider(
            responder=lambda _: "123456",
        )
    )

    service = ModelService(
        ModelRouter(registry),
        max_output_characters=5,
    )

    with pytest.raises(ModelProviderError) as exc_info:
        service.invoke(make_request())

    assert exc_info.value.code == "OUTPUT_LIMIT_EXCEEDED"


def test_provider_does_not_receive_unresolved_model() -> None:
    provider = DeterministicModelProvider()

    with pytest.raises(ModelContractError):
        provider.generate(make_request())


def test_deterministic_provider_is_repeatable() -> None:
    registry = ProviderRegistry()
    registry.register(DeterministicModelProvider())

    service = ModelService(ModelRouter(registry))

    first = service.invoke(make_request())
    second = service.invoke(
        ModelRequest(
            request_id="request-2",
            task_id="task-2",
            messages=(
                ModelMessage(
                    role=ModelRole.USER,
                    content="Hello Ann-E.",
                ),
            ),
        )
    )

    assert first.response.content == second.response.content
