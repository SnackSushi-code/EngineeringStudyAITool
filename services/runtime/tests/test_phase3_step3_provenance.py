from __future__ import annotations

import pytest

from anne_runtime.deterministic_provider import DeterministicModelProvider
from anne_runtime.model_contracts import (
    ModelMessage,
    ModelProviderError,
    ModelRequest,
    ModelRole,
)
from anne_runtime.model_router import ModelRouter
from anne_runtime.provider_registry import ProviderRegistry


def make_request(
    *,
    request_id="phase3-step3-request",
    task_id="phase3-step3-task",
    model=None,
):
    return ModelRequest(
        request_id=request_id,
        task_id=task_id,
        messages=(
            ModelMessage(
                role=ModelRole.USER,
                content="Phase 3 Step 3 provenance test request",
            ),
        ),
        model=model,
    )


class MismatchedResponseProvider(DeterministicModelProvider):
    def __init__(
        self,
        *,
        provider_id,
        models=("test-v1",),
        mismatch="provider_id",
    ):
        super().__init__(
            provider_id=provider_id,
            models=models,
        )
        self._mismatch = mismatch

    def generate(self, request):
        response = super().generate(request)

        if self._mismatch == "request_id":
            return response.__class__(
                request_id="wrong-request-id",
                task_id=response.task_id,
                provider_id=response.provider_id,
                model=response.model,
                content=response.content,
                provider_version=response.provider_version,
                finish_reason=response.finish_reason,
            )

        if self._mismatch == "task_id":
            return response.__class__(
                request_id=response.request_id,
                task_id="wrong-task-id",
                provider_id=response.provider_id,
                model=response.model,
                content=response.content,
                provider_version=response.provider_version,
                finish_reason=response.finish_reason,
            )

        if self._mismatch == "provider_id":
            return response.__class__(
                request_id=response.request_id,
                task_id=response.task_id,
                provider_id="wrong-provider",
                model=response.model,
                content=response.content,
                provider_version=response.provider_version,
                finish_reason=response.finish_reason,
            )

        if self._mismatch == "model":
            return response.__class__(
                request_id=response.request_id,
                task_id=response.task_id,
                provider_id=response.provider_id,
                model="wrong-model",
                content=response.content,
                provider_version=response.provider_version,
                finish_reason=response.finish_reason,
            )

        raise AssertionError(f"unknown mismatch: {self._mismatch}")


def test_successful_response_preserves_actual_provider_provenance():
    registry = ProviderRegistry()

    registry.register(
        DeterministicModelProvider(
            provider_id="fallback",
            models=("fallback-v1",),
        )
    )

    router = ModelRouter(registry)

    response = router.generate(make_request())

    assert response.provider_id == "fallback"
    assert response.model == "fallback-v1"


@pytest.mark.parametrize(
    "mismatch, expected_code",
    (
        ("request_id", "RESPONSE_CORRELATION_ERROR"),
        ("task_id", "RESPONSE_CORRELATION_ERROR"),
        ("provider_id", "RESPONSE_PROVENANCE_ERROR"),
        ("model", "RESPONSE_PROVENANCE_ERROR"),
    ),
)
def test_router_rejects_mismatched_provider_response(
    mismatch,
    expected_code,
):
    registry = ProviderRegistry()

    registry.register(
        MismatchedResponseProvider(
            provider_id="primary",
            models=("primary-v1",),
            mismatch=mismatch,
        )
    )

    router = ModelRouter(registry)

    with pytest.raises(ModelProviderError) as exc_info:
        router.generate(make_request())

    assert exc_info.value.code == expected_code
    assert exc_info.value.retryable is False


def test_retryable_provider_failure_then_successful_fallback_preserves_fallback_identity():
    class RetryableFailureProvider(DeterministicModelProvider):
        def generate(self, request):
            raise ModelProviderError(
                "temporary primary failure",
                code="TEMPORARY_PROVIDER_FAILURE",
                retryable=True,
            )

    registry = ProviderRegistry()

    registry.register(
        RetryableFailureProvider(
            provider_id="primary",
            models=("primary-v1",),
        )
    )

    registry.register(
        DeterministicModelProvider(
            provider_id="fallback",
            models=("fallback-v1",),
        )
    )

    router = ModelRouter(registry)

    response = router.generate(make_request())

    assert response.provider_id == "fallback"
    assert response.model == "fallback-v1"
