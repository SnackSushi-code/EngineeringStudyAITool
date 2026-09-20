from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .model_contracts import (
    FinishReason,
    ModelCapability,
    ModelContractError,
    ModelProviderDescriptor,
    ModelRequest,
    ModelResponse,
    ModelUsage,
)


class DeterministicModelProvider:
    """In-process provider for tests and development.

    This provider performs no network or OS operations.
    """

    def __init__(
        self,
        *,
        provider_id: str = "deterministic",
        provider_version: str = "1.0.0",
        models: tuple[str, ...] = ("deterministic-v1",),
        responder: Callable[[ModelRequest], str] | None = None,
    ) -> None:
        if not provider_id.strip():
            raise ModelContractError(
                "provider_id cannot be blank"
            )

        self._descriptor = ModelProviderDescriptor(
            provider_id=provider_id,
            provider_version=provider_version,
            models=models,
            capabilities=frozenset(
                {
                    ModelCapability.TEXT_INPUT,
                    ModelCapability.TEXT_OUTPUT,
                    ModelCapability.STRUCTURED_OUTPUT,
                }
            ),
        )

        self._responder = responder or self._default_responder

    @property
    def descriptor(self) -> ModelProviderDescriptor:
        return self._descriptor

    def generate(self, request: ModelRequest) -> ModelResponse:
        model = request.model

        if model is None:
            raise ModelContractError(
                "router must resolve a model before provider invocation"
            )

        if model not in self._descriptor.models:
            raise ModelContractError(
                f"unsupported deterministic model: {model}"
            )

        content = self._responder(request)

        if not isinstance(content, str):
            raise ModelContractError(
                "deterministic responder must return a string"
            )

        return ModelResponse(
            request_id=request.request_id,
            task_id=request.task_id,
            provider_id=self._descriptor.provider_id,
            provider_version=self._descriptor.provider_version,
            model=model,
            content=content,
            finish_reason=FinishReason.STOP,
            usage=ModelUsage(),
            raw_metadata={
                "deterministic": True,
            },
        )

    @staticmethod
    def _default_responder(request: ModelRequest) -> str:
        return (
            "Deterministic provider response for "
            f"{len(request.messages)} message(s)."
        )
