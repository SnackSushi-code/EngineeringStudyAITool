from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, Protocol, Sequence


MODEL_CONTRACT_VERSION = "1.0"


class ModelContractError(ValueError):
    """Raised when a model contract is invalid."""


class ModelProviderError(RuntimeError):
    """Raised when a provider cannot satisfy a model request."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class ModelRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class FinishReason(StrEnum):
    STOP = "stop"
    LENGTH = "length"
    TOOL_CALL = "tool_call"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"


class ModelCapability(StrEnum):
    TEXT_INPUT = "text_input"
    TEXT_OUTPUT = "text_output"
    STRUCTURED_OUTPUT = "structured_output"
    TOOL_CALLING = "tool_calling"
    STREAMING = "streaming"
    VISION = "vision"


@dataclass(frozen=True)
class ModelMessage:
    role: ModelRole
    content: str
    name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.content, str):
            raise ModelContractError("message content must be a string")

        if not self.content:
            raise ModelContractError("message content cannot be empty")

        if self.name is not None and not self.name.strip():
            raise ModelContractError("message name cannot be blank")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "role": self.role.value,
            "content": self.content,
        }

        if self.name is not None:
            result["name"] = self.name

        return result


@dataclass(frozen=True)
class ModelGenerationConfig:
    temperature: float = 0.2
    max_output_tokens: int = 2048
    top_p: float = 1.0
    stop_sequences: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= self.temperature <= 2.0:
            raise ModelContractError(
                "temperature must be between 0.0 and 2.0"
            )

        if self.max_output_tokens <= 0:
            raise ModelContractError(
                "max_output_tokens must be positive"
            )

        if not 0.0 < self.top_p <= 1.0:
            raise ModelContractError(
                "top_p must be greater than 0 and at most 1"
            )

        if any(not value for value in self.stop_sequences):
            raise ModelContractError(
                "stop sequences cannot contain empty strings"
            )


@dataclass(frozen=True)
class ModelRequest:
    request_id: str
    task_id: str
    messages: tuple[ModelMessage, ...]
    model: str | None = None
    required_capabilities: frozenset[ModelCapability] = frozenset()
    generation: ModelGenerationConfig = field(
        default_factory=ModelGenerationConfig
    )
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ModelContractError("request_id cannot be empty")

        if not self.task_id.strip():
            raise ModelContractError("task_id cannot be empty")

        if not self.messages:
            raise ModelContractError("model request requires at least one message")

        if self.model is not None and not self.model.strip():
            raise ModelContractError("model cannot be blank")

        for key, value in self.metadata.items():
            if not key.strip() or not value.strip():
                raise ModelContractError(
                    "metadata keys and values cannot be blank"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": MODEL_CONTRACT_VERSION,
            "request_id": self.request_id,
            "task_id": self.task_id,
            "model": self.model,
            "required_capabilities": sorted(
                capability.value
                for capability in self.required_capabilities
            ),
            "messages": [
                message.to_dict()
                for message in self.messages
            ],
            "generation": {
                "temperature": self.generation.temperature,
                "max_output_tokens": (
                    self.generation.max_output_tokens
                ),
                "top_p": self.generation.top_p,
                "stop_sequences": list(
                    self.generation.stop_sequences
                ),
            },
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("input_tokens", self.input_tokens),
            ("output_tokens", self.output_tokens),
            ("total_tokens", self.total_tokens),
        ):
            if value is not None and value < 0:
                raise ModelContractError(
                    f"{name} cannot be negative"
                )


@dataclass(frozen=True)
class ModelResponse:
    request_id: str
    task_id: str
    provider_id: str
    provider_version: str
    model: str
    content: str
    finish_reason: FinishReason
    usage: ModelUsage | None = None
    raw_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ModelContractError("response request_id cannot be empty")

        if not self.task_id.strip():
            raise ModelContractError("response task_id cannot be empty")

        if not self.provider_id.strip():
            raise ModelContractError("provider_id cannot be empty")

        if not self.provider_version.strip():
            raise ModelContractError(
                "provider_version cannot be empty"
            )

        if not self.model.strip():
            raise ModelContractError("response model cannot be empty")

        if not isinstance(self.content, str):
            raise ModelContractError("response content must be a string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": MODEL_CONTRACT_VERSION,
            "request_id": self.request_id,
            "task_id": self.task_id,
            "provider": {
                "id": self.provider_id,
                "version": self.provider_version,
            },
            "model": self.model,
            "content": self.content,
            "finish_reason": self.finish_reason.value,
            "usage": (
                None
                if self.usage is None
                else {
                    "input_tokens": self.usage.input_tokens,
                    "output_tokens": self.usage.output_tokens,
                    "total_tokens": self.usage.total_tokens,
                }
            ),
            "metadata": dict(self.raw_metadata),
        }


@dataclass(frozen=True)
class ModelProviderDescriptor:
    provider_id: str
    provider_version: str
    models: tuple[str, ...]
    capabilities: frozenset[ModelCapability]

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ModelContractError(
                "provider_id cannot be empty"
            )

        if not self.provider_version.strip():
            raise ModelContractError(
                "provider_version cannot be empty"
            )

        if not self.models:
            raise ModelContractError(
                "provider must expose at least one model"
            )

        if any(not model.strip() for model in self.models):
            raise ModelContractError(
                "provider model names cannot be blank"
            )

    def supports(
        self,
        required: Sequence[ModelCapability],
    ) -> bool:
        return set(required).issubset(self.capabilities)


class ModelProvider(Protocol):
    """Provider boundary.

    Providers must not silently gain operating-system privileges.
    Network-capable providers belong behind an authorized transport boundary.
    """

    @property
    def descriptor(self) -> ModelProviderDescriptor:
        ...

    def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate a model response for an already-authorized request."""
        ...
