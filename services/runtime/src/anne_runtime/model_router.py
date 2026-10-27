from __future__ import annotations

import time
from dataclasses import dataclass

from .model_contracts import (
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

    _DEFAULT_PROVIDER_FAILURE_THRESHOLD = 3
    _DEFAULT_PROVIDER_COOLDOWN_SECONDS = 30.0

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

        self._provider_failure_threshold = (
            self._DEFAULT_PROVIDER_FAILURE_THRESHOLD
        )
        self._provider_cooldown_seconds = (
            self._DEFAULT_PROVIDER_COOLDOWN_SECONDS
        )
        self._provider_failure_counts: dict[str, int] = {}
        self._provider_open_until: dict[str, float] = {}

    def _is_provider_open(self, provider_id: str) -> bool:
        open_until = self._provider_open_until.get(provider_id)

        if open_until is None:
            return False

        now = time.monotonic()

        if now >= open_until:
            self._provider_open_until.pop(provider_id, None)
            return False

        return True

    def _record_retryable_failure(self, provider_id: str) -> None:
        count = self._provider_failure_counts.get(provider_id, 0) + 1
        self._provider_failure_counts[provider_id] = count

        if count >= self._provider_failure_threshold:
            self._provider_open_until[provider_id] = (
                time.monotonic()
                + self._provider_cooldown_seconds
            )

    def _record_success(self, provider_id: str) -> None:
        self._provider_failure_counts[provider_id] = 0
        self._provider_open_until.pop(provider_id, None)

    def _eligible_candidates(
        self,
        request: ModelRequest,
    ):
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

        return candidates

    def _resolve_model(
        self,
        provider,
        request: ModelRequest,
    ) -> str:
        model = request.model

        if model is None:
            if (
                self._default_model is not None
                and self._default_model in provider.descriptor.models
            ):
                model = self._default_model
            else:
                model = provider.descriptor.models[0]

        return model

    def resolve(
        self,
        request: ModelRequest,
    ) -> ModelRoute:
        candidates = self._eligible_candidates(request)

        for provider in candidates:
            provider_id = provider.descriptor.provider_id

            if self._is_provider_open(provider_id):
                continue

            model = self._resolve_model(provider, request)

            return ModelRoute(
                provider_id=provider_id,
                model=model,
            )

        raise ModelProviderError(
            "all eligible model providers are temporarily unavailable",
            code="ALL_PROVIDERS_OPEN",
            retryable=True,
        )

    def generate(self, request: ModelRequest) -> ModelResponse:
        candidates = self._eligible_candidates(request)

        failures: list[ModelProviderError] = []

        for provider in candidates:
            provider_id = provider.descriptor.provider_id

            if self._is_provider_open(provider_id):
                continue

            model = self._resolve_model(provider, request)

            routed_request = ModelRequest(
                request_id=request.request_id,
                task_id=request.task_id,
                messages=request.messages,
                model=model,
                required_capabilities=request.required_capabilities,
                generation=request.generation,
                metadata=request.metadata,
            )

            try:
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

                if response.provider_id != provider_id:
                    raise ModelProviderError(
                        "provider response provider_id does not match provider",
                        code="RESPONSE_PROVENANCE_ERROR",
                        retryable=False,
                    )

                if response.model != model:
                    raise ModelProviderError(
                        "provider response model does not match selected model",
                        code="RESPONSE_PROVENANCE_ERROR",
                        retryable=False,
                    )

                self._record_success(provider_id)

                return response

            except ModelProviderError as exc:
                if not exc.retryable:
                    raise

                self._record_retryable_failure(provider_id)
                failures.append(exc)

        if failures:
            raise ModelProviderError(
                "all eligible model providers failed",
                code="ALL_PROVIDERS_FAILED",
                retryable=True,
            )

        raise ModelProviderError(
            "all eligible model providers are temporarily unavailable",
            code="ALL_PROVIDERS_OPEN",
            retryable=True,
        )
