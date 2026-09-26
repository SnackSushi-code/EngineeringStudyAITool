from __future__ import annotations

from threading import RLock

from .model_contracts import (
    ModelContractError,
    ModelProvider,
    ModelProviderDescriptor,
)


class ProviderRegistry:
    """Thread-safe registry of explicitly installed model providers."""

    def __init__(self) -> None:
        self._providers: dict[str, ModelProvider] = {}
        self._lock = RLock()

    def register(
        self,
        provider: ModelProvider,
        *,
        replace: bool = False,
    ) -> None:
        descriptor = provider.descriptor
        provider_id = descriptor.provider_id

        with self._lock:
            if provider_id in self._providers and not replace:
                raise ModelContractError(
                    f"provider already registered: {provider_id}"
                )

            self._providers[provider_id] = provider

    def unregister(self, provider_id: str) -> ModelProvider:
        if not provider_id.strip():
            raise ModelContractError(
                "provider_id cannot be blank"
            )

        with self._lock:
            try:
                return self._providers.pop(provider_id)
            except KeyError as exc:
                raise ModelContractError(
                    f"provider is not registered: {provider_id}"
                ) from exc

    def get(self, provider_id: str) -> ModelProvider:
        if not provider_id.strip():
            raise ModelContractError(
                "provider_id cannot be blank"
            )

        with self._lock:
            try:
                return self._providers[provider_id]
            except KeyError as exc:
                raise ModelContractError(
                    f"provider is not registered: {provider_id}"
                ) from exc

    def list_descriptors(self) -> tuple[ModelProviderDescriptor, ...]:
        with self._lock:
            return tuple(
                provider.descriptor
                for provider in self._providers.values()
            )

    def providers(self) -> tuple[ModelProvider, ...]:
        with self._lock:
            return tuple(self._providers.values())

    def __len__(self) -> int:
        with self._lock:
            return len(self._providers)
