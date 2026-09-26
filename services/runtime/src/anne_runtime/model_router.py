from __future__ import annotations

from dataclasses import dataclass

from .model_contracts import (
    ModelCapability,
    ModelContractError,
    ModelProvider,
    ModelProviderError,
    ModelRequest,
    ModelResponse,
)
from .provider_registry import ProviderRegistry


@dataclass(frozen=True)
class ModelRoute:
    provider_id: str
    model: str


class ModelRouter:
    """Deterministic model routing over explicitly registered providers."""

    def __init__(
        self,
        registry: ProviderRegistry,
        *,
        default_provider_id: str | None = None,
        default_model: str | None = None,
    ) -> None:
        self._registry = registry
        self._default_provider_id = default_provider_id
        self._default_model = default_model

    def resolve(
        self,
        request: ModelRequest,
    ) -> ModelRoute:
        candidates = list(self._registry.providers())

        if not candidates:
            raise ModelProviderError(
                "no model providers are registered",
                code="NO_PROVIDERS",
                retryable=False,
            )

        if request.model is not None:
            candidates = [
                provider
                for provider in candidates
                if request.model in provider.descriptor.models
            ]

        if request.required_capabilities:
            candidates = [
                provider
                for provider in candidates
                if provider.descriptor.supports(
                    tuple(request.required_capabilities)
                )
            ]

        if request.model is None and self._default_provider_id:
            candidates = [
                provider
                for provider in candidates
                if provider.descriptor.provider_id
                == self._default_provider_id
            ]

        if (
            request.model is None
            and self._default_model is not None
        ):
            candidates = [
                provider
                for provider in candidates
                if self._default_model in provider.descriptor.models
            ]

        if not candidates:
            raise ModelProviderError(
                "no registered provider satisfies the model request",
                code="NO_ROUTE",
                retryable=False,
            )

        # Registry insertion order is deterministic. Routing intentionally
        # does not invent a quality ranking between providers.
        provider = candidates[0]

        model = request.model

        if model is None:
            if (
                self._default_model is not None
                and self._default_model in provider.descriptor.models
            ):
                model = self._default_model
            else:
                model = provider.descriptor.models[0]

        return ModelRoute(
            provider_id=provider.descriptor.provider_id,
            model=model,
        )

    def generate(self, request: ModelRequest) -> ModelResponse:
        route = self.resolve(request)
        provider = self._registry.get(route.provider_id)

        routed_request = ModelRequest(
            request_id=request.request_id,
            task_id=request.task_id,
            messages=request.messages,
            model=route.model,
            required_capabilities=request.required_capabilities,
            generation=request.generation,
            metadata=request.metadata,
        )

        response = provider.generate(routed_request)

        if response.request_id != request.request_id:
            raise ModelProviderError(
                "provider response request_id does not match request",
                code="RESPONSE_CORRELATION_ERROR",
                retryable=False,
            )

        if response.task_id != request.task_id:
            raise ModelProviderError(
                "provider response task_id does not match request",
                code="RESPONSE_CORRELATION_ERROR",
                retryable=False,
            )

        if response.provider_id != provider.descriptor.provider_id:
            raise ModelProviderError(
                "provider response provider_id does not match provider",
                code="RESPONSE_PROVENANCE_ERROR",
                retryable=False,
            )

        if response.model != route.model:
            raise ModelProviderError(
                "provider response model does not match selected model",
                code="RESPONSE_PROVENANCE_ERROR",
                retryable=False,
            )

        return response
