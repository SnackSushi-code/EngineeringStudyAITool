from __future__ import annotations

import os

from .deterministic_provider import DeterministicModelProvider
from .gemini_provider import GeminiModelProvider
from .provider_registry import ProviderRegistry
from .model_router import ModelRouter
from .model_service import ModelService


MODEL_PROVIDER_ENV = "ANNE_MODEL_PROVIDER"
MODEL_NAME_ENV = "ANNE_MODEL_NAME"
GEMINI_MODEL_ENV = "ANNE_GEMINI_MODEL"

DETERMINISTIC_PROVIDER_ID = "deterministic"
DETERMINISTIC_MODEL = "deterministic-v1"

GEMINI_PROVIDER_ID = "gemini"
GEMINI_MODEL = "gemini-3.5-flash-lite"


class ModelProviderConfigurationError(ValueError):
    """Raised when runtime model-provider configuration is invalid."""


class ModelProviderFactory:
    """Build the runtime model provider registry and router."""

    def __init__(self, *, deterministic_responder) -> None:
        self._deterministic_responder = deterministic_responder

    def build_model_service(self) -> ModelService:
        providers = ProviderRegistry()

        providers.register(
            DeterministicModelProvider(
                responder=self._deterministic_responder,
            )
        )

        selected_provider = (
            os.getenv(MODEL_PROVIDER_ENV)
            or DETERMINISTIC_PROVIDER_ID
        ).strip().lower()

        selected_model = (
            os.getenv(MODEL_NAME_ENV)
            or ""
        ).strip()

        if selected_provider == GEMINI_PROVIDER_ID:
            gemini_model = (
                selected_model
                or os.getenv(GEMINI_MODEL_ENV)
                or GEMINI_MODEL
            ).strip()

            if not gemini_model:
                raise ModelProviderConfigurationError(
                    "Gemini model selection cannot be blank."
                )

            providers.register(
                GeminiModelProvider(
                    model=gemini_model,
                )
            )

            return ModelService(
                ModelRouter(
                    providers,
                    default_provider_id=GEMINI_PROVIDER_ID,
                    default_model=gemini_model,
                )
            )

        if selected_provider == DETERMINISTIC_PROVIDER_ID:
            deterministic_model = (
                selected_model
                or DETERMINISTIC_MODEL
            ).strip()

            if deterministic_model != DETERMINISTIC_MODEL:
                raise ModelProviderConfigurationError(
                    "Unsupported deterministic model: "
                    f"{deterministic_model}"
                )

            return ModelService(
                ModelRouter(
                    providers,
                    default_provider_id=DETERMINISTIC_PROVIDER_ID,
                    default_model=DETERMINISTIC_MODEL,
                )
            )

        raise ModelProviderConfigurationError(
            f"Unsupported model provider: {selected_provider}"
        )
