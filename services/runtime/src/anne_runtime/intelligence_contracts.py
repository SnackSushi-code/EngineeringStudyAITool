from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping
from uuid import UUID

from .model_contracts import ModelMessage, ModelRequest, ModelRole

INTELLIGENCE_CONTRACT_VERSION = "1.0"


class IntelligenceContractError(ValueError):
    """Invalid intelligence-layer contract."""


@dataclass(frozen=True)
class IntelligenceToolProposal:
    """Model-owned tool intent; runtime authority is resolved separately."""
    request_id: UUID
    task_id: UUID
    tool: str
    operation: str
    arguments: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.tool.strip():
            raise IntelligenceContractError("tool must be nonblank")
        if not self.operation.strip():
            raise IntelligenceContractError("operation must be nonblank")
        if not isinstance(self.arguments, Mapping):
            raise IntelligenceContractError("arguments must be a mapping")
        object.__setattr__(self, "arguments", dict(self.arguments))

    def to_dict(self) -> dict[str, Any]:
        """Serialize model-owned intent only; never serialize runtime authority."""
        return {
            "request_id": str(self.request_id),
            "task_id": str(self.task_id),
            "tool": self.tool,
            "operation": self.operation,
            "arguments": dict(self.arguments),
        }


class IntelligenceDecisionType(StrEnum):
    FINAL_RESPONSE = "FINAL_RESPONSE"
    TOOL_PROPOSAL = "TOOL_PROPOSAL"


@dataclass(frozen=True)
class IntelligenceRequest:
    """Runtime request entering the intelligence boundary."""

    request_id: UUID
    task_id: UUID
    user_intent: str
    conversation: tuple[Mapping[str, Any], ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, UUID):
            raise IntelligenceContractError("request_id must be a UUID")
        if not isinstance(self.task_id, UUID):
            raise IntelligenceContractError("task_id must be a UUID")
        if not isinstance(self.user_intent, str) or not self.user_intent.strip():
            raise IntelligenceContractError("user_intent must be a non-empty string")

        for item in self.conversation:
            if not isinstance(item, Mapping):
                raise IntelligenceContractError(
                    "conversation entries must be mappings"
                )

        for key, value in self.metadata.items():
            if not isinstance(key, str) or not key.strip():
                raise IntelligenceContractError(
                    "metadata keys must be non-empty strings"
                )
            if not isinstance(value, str):
                raise IntelligenceContractError(
                    "metadata values must be strings"
                )

    @property
    def model_request_id(self) -> str:
        return str(self.request_id)

    @property
    def model_task_id(self) -> str:
        return str(self.task_id)

    def to_model_request(self) -> ModelRequest:
        messages = [
            ModelMessage(
                role=ModelRole.USER,
                content=self.user_intent,
            )
        ]

        for item in self.conversation:
            role_value = item.get("role")
            content = item.get("content")
            name = item.get("name")

            if not isinstance(role_value, str) or not role_value.strip():
                raise IntelligenceContractError(
                    "conversation role must be a non-empty string"
                )
            if not isinstance(content, str):
                raise IntelligenceContractError(
                    "conversation content must be a string"
                )
            if name is not None and not isinstance(name, str):
                raise IntelligenceContractError(
                    "conversation name must be a string when provided"
                )

            try:
                role = ModelRole(role_value)
            except ValueError as exc:
                raise IntelligenceContractError(
                    f"unsupported conversation role: {role_value}"
                ) from exc

            messages.append(
                ModelMessage(
                    role=role,
                    content=content,
                    name=name,
                )
            )

        return ModelRequest(
            request_id=self.model_request_id,
            task_id=self.model_task_id,
            messages=tuple(messages),
            metadata=dict(self.metadata),
        )
    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": INTELLIGENCE_CONTRACT_VERSION,
            "request_id": str(self.request_id),
            "task_id": str(self.task_id),
            "user_intent": self.user_intent,
            "conversation": [dict(item) for item in self.conversation],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class IntelligenceDecision:
    """Validated intelligence outcome; a tool proposal is not authority."""

    decision_type: IntelligenceDecisionType
    response_text: str | None = None
    tool_call: IntelligenceToolProposal | None = None

    def __post_init__(self) -> None:
        if self.decision_type == IntelligenceDecisionType.FINAL_RESPONSE:
            if self.response_text is None or not self.response_text.strip():
                raise IntelligenceContractError(
                    "FINAL_RESPONSE requires response_text"
                )
            if self.tool_call is not None:
                raise IntelligenceContractError(
                    "FINAL_RESPONSE cannot contain tool_call"
                )
        elif self.decision_type == IntelligenceDecisionType.TOOL_PROPOSAL:
            if self.tool_call is None:
                raise IntelligenceContractError(
                    "TOOL_PROPOSAL requires tool_call"
                )
            if self.response_text is not None:
                raise IntelligenceContractError(
                    "TOOL_PROPOSAL cannot contain response_text"
                )
        else:
            raise IntelligenceContractError(
                f"Unsupported decision type: {self.decision_type}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": INTELLIGENCE_CONTRACT_VERSION,
            "decision_type": self.decision_type.value,
            "response_text": self.response_text,
            "tool_call": (
                None
                if self.tool_call is None
                else self.tool_call.to_dict()
            ),
        }


@dataclass(frozen=True)
class IntelligenceResult:
    """Validated result crossing the intelligence boundary."""

    request: IntelligenceRequest
    decision: IntelligenceDecision
    model_request_id: str
    model_task_id: str

    def __post_init__(self) -> None:
        if self.model_request_id != self.request.model_request_id:
            raise IntelligenceContractError(
                "model_request_id correlation mismatch"
            )
        if self.model_task_id != self.request.model_task_id:
            raise IntelligenceContractError(
                "model_task_id correlation mismatch"
            )

        call = self.decision.tool_call
        if call is not None:
            if call.request_id != self.request.request_id:
                raise IntelligenceContractError(
                    "tool_call request_id correlation mismatch"
                )
            if call.task_id != self.request.task_id:
                raise IntelligenceContractError(
                    "tool_call task_id correlation mismatch"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": INTELLIGENCE_CONTRACT_VERSION,
            "request": self.request.to_dict(),
            "decision": self.decision.to_dict(),
            "model_request_id": self.model_request_id,
            "model_task_id": self.model_task_id,
        }
