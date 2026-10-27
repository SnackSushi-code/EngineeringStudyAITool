from __future__ import annotations

import pytest

from anne_runtime.deterministic_provider import (
    DeterministicModelProvider,
)
from anne_runtime.model_contracts import (
    ModelCapability,
    ModelMessage,
    ModelProviderError,
    ModelRequest,
    ModelRole,
)
from anne_runtime.model_router import ModelRouter
from anne_runtime.provider_registry import ProviderRegistry


def make_request(
    *,
    request_id="phase3-request",
    task_id="phase3-task",
    capabilities=(),
    model=None,
):
    return ModelRequest(
        request_id=request_id,
        task_id=task_id,
        messages=(
            ModelMessage(
                role=ModelRole.USER,
                content="Phase 3 routing test request",
            ),
        ),
        model=model,
        required_capabilities=frozenset(capabilities),
    )


def test_router_selects_provider_by_required_capability():
    """
    Phase 3 requirement:
    provider selection must be based on provider capabilities,
    not Gemini-specific routing logic.
    """
    registry = ProviderRegistry()

    provider = DeterministicModelProvider(
        provider_id="deterministic",
        models=("deterministic-v1",),
    )

    registry.register(provider)

    router = ModelRouter(registry)

    request = make_request(
        capabilities=(ModelCapability.TEXT_OUTPUT,),
    )

    route = router.resolve(request)

    assert route.provider_id == "deterministic"
    assert route.model == "deterministic-v1"


def test_router_respects_explicit_provider_selection():
    """
    An explicit provider preference must be honored when that
    provider is eligible.
    """
    registry = ProviderRegistry()

    registry.register(
        DeterministicModelProvider(
            provider_id="deterministic",
            models=("deterministic-v1",),
        )
    )

    registry.register(
        DeterministicModelProvider(
            provider_id="alternate",
            models=("alternate-v1",),
        )
    )

    router = ModelRouter(
        registry,
        default_provider_id="alternate",
    )

    request = make_request()

    route = router.resolve(request)

    assert route.provider_id == "alternate"
    assert route.model == "alternate-v1"


def test_router_fails_closed_when_no_provider_is_eligible():
    """
    No eligible provider must produce a deterministic routing failure
    rather than silently selecting an incompatible provider.
    """
    registry = ProviderRegistry()

    registry.register(
        DeterministicModelProvider(
            provider_id="deterministic",
        )
    )

    router = ModelRouter(registry)

    request = make_request(
        capabilities=("phase3.nonexistent.capability",),
    )

    with pytest.raises(ModelProviderError) as exc_info:
        router.resolve(request)

    assert exc_info.value.code == "NO_ROUTE"
    assert exc_info.value.retryable is False


class FailingModelProvider(DeterministicModelProvider):
    def __init__(
        self,
        *,
        provider_id,
        models=("test-v1",),
        error_code="TEMPORARY_PROVIDER_FAILURE",
        retryable=True,
    ):
        super().__init__(
            provider_id=provider_id,
            models=models,
        )
        self._error_code = error_code
        self._retryable = retryable

    def generate(self, request):
        raise ModelProviderError(
            f"test provider failure: {self._error_code}",
            code=self._error_code,
            retryable=self._retryable,
        )


def test_router_falls_back_after_retryable_provider_failure():
    """
    A retryable provider failure must allow the router to continue
    to the next eligible provider.
    """
    registry = ProviderRegistry()

    registry.register(
        FailingModelProvider(
            provider_id="primary",
            models=("primary-v1",),
            error_code="TEMPORARY_PROVIDER_FAILURE",
            retryable=True,
        )
    )

    registry.register(
        DeterministicModelProvider(
            provider_id="fallback",
            models=("fallback-v1",),
        )
    )

    router = ModelRouter(registry)

    request = make_request()

    response = router.generate(request)

    assert response.provider_id == "fallback"
    assert response.model == "fallback-v1"


def test_router_does_not_fallback_after_non_retryable_failure():
    """
    A non-retryable provider failure must terminate routing rather
    than silently switching providers.
    """
    registry = ProviderRegistry()

    registry.register(
        FailingModelProvider(
            provider_id="primary",
            models=("primary-v1",),
            error_code="PERMANENT_PROVIDER_FAILURE",
            retryable=False,
        )
    )

    registry.register(
        DeterministicModelProvider(
            provider_id="fallback",
            models=("fallback-v1",),
        )
    )

    router = ModelRouter(registry)

    request = make_request()

    with pytest.raises(ModelProviderError) as exc_info:
        router.generate(request)

    assert exc_info.value.code == "PERMANENT_PROVIDER_FAILURE"
    assert exc_info.value.retryable is False


def test_router_does_not_fallback_after_security_failure():
    """
    Security/authorization failures must remain terminal and must
    never be bypassed by selecting another provider.
    """
    registry = ProviderRegistry()

    registry.register(
        FailingModelProvider(
            provider_id="primary",
            models=("primary-v1",),
            error_code="AUTHORIZATION_DENIED",
            retryable=False,
        )
    )

    registry.register(
        DeterministicModelProvider(
            provider_id="fallback",
            models=("fallback-v1",),
        )
    )

    router = ModelRouter(registry)

    request = make_request()

    with pytest.raises(ModelProviderError) as exc_info:
        router.generate(request)

    assert exc_info.value.code == "AUTHORIZATION_DENIED"
    assert exc_info.value.retryable is False


def test_router_fails_when_all_eligible_providers_fail():
    """
    If every eligible provider fails retryably, routing must return
    a deterministic final provider failure rather than succeeding
    with an incompatible or unverified provider.
    """
    registry = ProviderRegistry()

    registry.register(
        FailingModelProvider(
            provider_id="primary",
            models=("primary-v1",),
            error_code="PRIMARY_TEMPORARY_FAILURE",
            retryable=True,
        )
    )

    registry.register(
        FailingModelProvider(
            provider_id="secondary",
            models=("secondary-v1",),
            error_code="SECONDARY_TEMPORARY_FAILURE",
            retryable=True,
        )
    )

    router = ModelRouter(registry)

    request = make_request()

    with pytest.raises(ModelProviderError) as exc_info:
        router.generate(request)

    assert exc_info.value.retryable is True
    assert exc_info.value.code == "ALL_PROVIDERS_FAILED"
