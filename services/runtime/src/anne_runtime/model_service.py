from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from .model_contracts import (
    ModelProviderError,
    ModelRequest,
    ModelResponse,
)
from .model_router import ModelRoute, ModelRouter


@dataclass(frozen=True)
class ModelInvocation:
    request: ModelRequest
    route: ModelRoute
    response: ModelResponse
    duration_seconds: float


class ModelService:
    """High-level model invocation boundary.

    The service owns request/response correlation and timing metadata.
    It deliberately does not perform authorization itself; authorization
    belongs to the policy/tool orchestration layer that invokes this service.
    """

    def __init__(
        self,
        router: ModelRouter,
        *,
        max_input_characters: int = 1_000_000,
        max_output_characters: int = 1_000_000,
    ) -> None:
        if max_input_characters <= 0:
            raise ValueError(
                "max_input_characters must be positive"
            )

        if max_output_characters <= 0:
            raise ValueError(
                "max_output_characters must be positive"
            )

        self._router = router
        self._max_input_characters = max_input_characters
        self._max_output_characters = max_output_characters

    def invoke(self, request: ModelRequest) -> ModelInvocation:
        input_characters = sum(
            len(message.content)
            for message in request.messages
        )

        if input_characters > self._max_input_characters:
            raise ModelProviderError(
                "model input exceeds configured character limit",
                code="INPUT_LIMIT_EXCEEDED",
                retryable=False,
            )

        route = self._router.resolve(request)

        started = monotonic()

        response = self._router.generate(request)

        duration = monotonic() - started

        if len(response.content) > self._max_output_characters:
            raise ModelProviderError(
                "model output exceeds configured character limit",
                code="OUTPUT_LIMIT_EXCEEDED",
                retryable=False,
            )

        return ModelInvocation(
            request=request,
            route=route,
            response=response,
            duration_seconds=duration,
        )
