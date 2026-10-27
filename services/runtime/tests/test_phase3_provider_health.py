from __future__ import annotations

import time

import pytest

from anne_runtime.deterministic_provider import (
    DeterministicModelProvider,
)
from anne_runtime.model_contracts import (
    ModelMessage,
    ModelProviderError,
    ModelRequest,
    ModelRole,
)
from anne_runtime.model_router import ModelRouter
from anne_runtime.provider_registry import ProviderRegistry


def make_request() -> ModelRequest:
    return ModelRequest(
        request_id="phase3-health-request",
        task_id="phase3-health-task",
        messages=(
            ModelMessage(
                role=ModelRole.USER,
                content="provider health test",
            ),
        ),
        model=None,
        required_capabilities=(),
        generation=None,
        metadata={},
    )


class FailingModelProvider:
    def __init__(
        self,
        provider_id,
        models,
        error_code="TEMPORARY_PROVIDER_FAILURE",
        retryable=True,
    ):
        self._descriptor = type(
            "Descriptor",
            (),
            {
                "provider_id": provider_id,
                "models": models,
                "supports": lambda self, capabilities: True,
            },
        )()
        self._error_code = error_code
        self._retryable = retryable

    @property
    def descriptor(self):
        return self._descriptor

    def generate(self, request):
        raise ModelProviderError(
            f"test provider failure: {self._error_code}",
            code=self._error_code,
            retryable=self._retryable,
        )


def test_router_exposes_provider_health_defaults():
    registry = ProviderRegistry()

    router = ModelRouter(registry)

    assert router._provider_failure_threshold == 3
    assert router._provider_cooldown_seconds == 30.0
    assert router._provider_failure_counts == {}
    assert router._provider_open_until == {}


def test_retryable_failures_are_tracked_per_provider():
    registry = ProviderRegistry()

    registry.register(
        FailingModelProvider(
            provider_id="primary",
            models=("primary-v1",),
        )
    )

    router = ModelRouter(registry)
    request = make_request()

    for _ in range(2):
        with pytest.raises(ModelProviderError):
            router.generate(request)

    assert router._provider_failure_counts["primary"] == 2
    assert "primary" not in router._provider_open_until


def test_provider_circuit_opens_at_failure_threshold():
    registry = ProviderRegistry()

    registry.register(
        FailingModelProvider(
            provider_id="primary",
            models=("primary-v1",),
        )
    )

    router = ModelRouter(registry)
    request = make_request()

    for _ in range(3):
        with pytest.raises(ModelProviderError):
            router.generate(request)

    assert router._provider_failure_counts["primary"] == 3
    assert router._provider_open_until["primary"] > time.monotonic()


def test_open_provider_is_skipped_and_fallback_is_used():
    # First establish the primary provider's open circuit using a
    # registry containing only the failing provider.
    failing_registry = ProviderRegistry()

    failing_registry.register(
        FailingModelProvider(
            provider_id="primary",
            models=("primary-v1",),
        )
    )

    failing_router = ModelRouter(failing_registry)
    request = make_request()

    for _ in range(3):
        with pytest.raises(ModelProviderError):
            failing_router.generate(request)

    assert failing_router._provider_failure_counts["primary"] == 3
    assert failing_router._provider_open_until["primary"] > time.monotonic()

    # A normal router with the same provider ordering skips an open
    # primary and uses the healthy fallback.
    registry = ProviderRegistry()

    registry.register(
        FailingModelProvider(
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
    router._provider_failure_counts["primary"] = 3
    router._provider_open_until["primary"] = time.monotonic() + 30.0

    response = router.generate(request)

    assert response.provider_id == "fallback"
    assert router._provider_failure_counts["primary"] == 3
    assert router._provider_open_until["primary"] > time.monotonic()

def test_successful_provider_resets_failure_count():
    registry = ProviderRegistry()

    class FailOnceProvider(DeterministicModelProvider):
        def __init__(self):
            super().__init__(
                provider_id="primary",
                models=("primary-v1",),
            )
            self.failed = False

        def generate(self, request):
            if not self.failed:
                self.failed = True
                raise ModelProviderError(
                    "temporary failure",
                    code="TEMPORARY_PROVIDER_FAILURE",
                    retryable=True,
                )

            return super().generate(request)

    class FallbackProvider(DeterministicModelProvider):
        def __init__(self):
            super().__init__(
                provider_id="fallback",
                models=("fallback-v1",),
            )

    primary = FailOnceProvider()
    fallback = FallbackProvider()

    registry.register(primary)
    registry.register(fallback)

    router = ModelRouter(registry)
    request = make_request()

    # First call: primary fails once, fallback succeeds.
    response = router.generate(request)

    assert response.provider_id == "fallback"
    assert router._provider_failure_counts["primary"] == 1

    # The primary provider is still eligible because it has not reached
    # the circuit threshold. Its next successful generation resets health.
    response = router.generate(request)

    assert response.provider_id == "primary"
    assert router._provider_failure_counts["primary"] == 0
    assert "primary" not in router._provider_open_until


def test_non_retryable_failure_does_not_change_provider_health():
    registry = ProviderRegistry()

    registry.register(
        FailingModelProvider(
            provider_id="primary",
            models=("primary-v1",),
            error_code="PERMANENT_PROVIDER_FAILURE",
            retryable=False,
        )
    )

    router = ModelRouter(registry)
    request = make_request()

    with pytest.raises(ModelProviderError) as exc_info:
        router.generate(request)

    assert exc_info.value.code == "PERMANENT_PROVIDER_FAILURE"
    assert router._provider_failure_counts.get("primary", 0) == 0
    assert "primary" not in router._provider_open_until


def test_provider_reopens_after_cooldown():
    registry = ProviderRegistry()

    class FailThreeThenSucceedProvider:
        def __init__(self):
            self._descriptor = type(
                "Descriptor",
                (),
                {
                    "provider_id": "primary",
                    "models": ("primary-v1",),
                    "supports": lambda self, capabilities: True,
                },
            )()
            self.calls = 0

        @property
        def descriptor(self):
            return self._descriptor

        def generate(self, request):
            self.calls += 1

            if self.calls <= 3:
                raise ModelProviderError(
                    "temporary failure",
                    code="TEMPORARY_PROVIDER_FAILURE",
                    retryable=True,
                )

            return DeterministicModelProvider(
                provider_id="primary",
                models=("primary-v1",),
            ).generate(request)

    provider = FailThreeThenSucceedProvider()
    registry.register(provider)

    router = ModelRouter(registry)
    request = make_request()

    for _ in range(3):
        with pytest.raises(ModelProviderError):
            router.generate(request)

    assert router._provider_failure_counts["primary"] == 3

    # Force the cooldown to expire without waiting 30 real seconds.
    router._provider_open_until["primary"] = time.monotonic() - 1.0

    response = router.generate(request)

    assert response.provider_id == "primary"
    assert router._provider_failure_counts["primary"] == 0
    assert "primary" not in router._provider_open_until
