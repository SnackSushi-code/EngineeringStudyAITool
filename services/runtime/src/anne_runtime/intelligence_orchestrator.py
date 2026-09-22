from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any, Mapping
from uuid import UUID

from .intelligence_contracts import (
    IntelligenceContractError,
    IntelligenceDecision,
    IntelligenceDecisionType,
    IntelligenceRequest,
    IntelligenceResult,
    IntelligenceToolProposal,
)
from .intelligence_tool_authority import ToolCapabilityCatalog
from .model_contracts import FinishReason
from .model_service import ModelService


class IntelligenceOrchestrationError(RuntimeError):
    """Raised when intelligence orchestration cannot produce a valid decision."""


@dataclass(frozen=True)
class IntelligenceInvocation:
    """Validated intelligence result plus model execution metadata."""

    result: IntelligenceResult
    provider_id: str
    provider_version: str
    model: str
    finish_reason: FinishReason
    duration_seconds: float


class IntelligenceOrchestrator:
    """Turn model output into validated intelligence decisions.

    This component never invokes a tool handler. A TOOL_PROPOSAL remains data
    until it is handed to the existing runtime/task execution boundary.
    """

    RESPONSE_CONTRACT_VERSION = "1.0"

    def __init__(
        self,
        model_service: ModelService,
        capability_catalog: ToolCapabilityCatalog | None = None,
    ) -> None:
        self._model_service = model_service
        self._capability_catalog = capability_catalog

    def process(self, request: IntelligenceRequest) -> IntelligenceInvocation:
        if not isinstance(request, IntelligenceRequest):
            raise IntelligenceOrchestrationError(
                "request must be an IntelligenceRequest"
            )

        model_request = request.to_model_request()
        if self._capability_catalog is not None:
            model_request = replace(
                model_request,
                metadata={
                    **dict(model_request.metadata),
                    "anne.tool_catalog": self._capability_catalog.as_metadata_json(),
                },
            )

        try:
            invocation = self._model_service.invoke(model_request)
        except Exception as exc:
            raise IntelligenceOrchestrationError(
                f"model invocation failed: {type(exc).__name__}"
            ) from exc

        response = invocation.response

        if response.request_id != request.model_request_id:
            raise IntelligenceOrchestrationError(
                "model response request_id correlation mismatch"
            )

        if response.task_id != request.model_task_id:
            raise IntelligenceOrchestrationError(
                "model response task_id correlation mismatch"
            )

        if response.finish_reason != FinishReason.STOP:
            raise IntelligenceOrchestrationError(
                f"unsupported model finish reason: {response.finish_reason.value}"
            )

        decision = self._decode_decision(response.content, request)

        result = IntelligenceResult(
            request=request,
            decision=decision,
            model_request_id=response.request_id,
            model_task_id=response.task_id,
        )

        return IntelligenceInvocation(
            result=result,
            provider_id=response.provider_id,
            provider_version=response.provider_version,
            model=response.model,
            finish_reason=response.finish_reason,
            duration_seconds=invocation.duration_seconds,
        )

    def _decode_decision(
        self,
        content: str,
        request: IntelligenceRequest,
    ) -> IntelligenceDecision:
        try:
            payload = json.loads(content)
        except (json.JSONDecodeError, TypeError) as exc:
            raise IntelligenceOrchestrationError(
                "model response is not valid JSON"
            ) from exc

        if not isinstance(payload, Mapping):
            raise IntelligenceOrchestrationError("model response must be a JSON object")

        version = payload.get(
            "contract_version",
            self.RESPONSE_CONTRACT_VERSION,
        )
        if version != self.RESPONSE_CONTRACT_VERSION:
            raise IntelligenceOrchestrationError(
                f"unsupported intelligence response contract version: {version!r}"
            )

        try:
            decision_type = IntelligenceDecisionType(payload.get("decision_type"))
        except (ValueError, TypeError) as exc:
            raise IntelligenceOrchestrationError(
                "model response contains an unsupported decision_type"
            ) from exc

        if decision_type == IntelligenceDecisionType.FINAL_RESPONSE:
            response_text = payload.get("response_text")

            if not isinstance(response_text, str) or not response_text.strip():
                raise IntelligenceOrchestrationError(
                    "FINAL_RESPONSE requires non-empty response_text"
                )

            if payload.get("tool_call") is not None:
                raise IntelligenceOrchestrationError(
                    "FINAL_RESPONSE cannot contain tool_call"
                )

            return IntelligenceDecision(
                decision_type=decision_type,
                response_text=response_text,
            )

        if payload.get("response_text") is not None:
            raise IntelligenceOrchestrationError(
                "TOOL_PROPOSAL cannot contain response_text"
            )

        raw_call = payload.get("tool_call")
        if not isinstance(raw_call, Mapping):
            raise IntelligenceOrchestrationError(
                "TOOL_PROPOSAL requires a tool_call object"
            )

        try:
            tool_call = self._decode_tool_call(raw_call, request)
            return IntelligenceDecision(
                decision_type=decision_type,
                tool_call=tool_call,
            )
        except (KeyError, TypeError, ValueError, IntelligenceContractError) as exc:
            raise IntelligenceOrchestrationError(
                "model response contains an invalid tool_call"
            ) from exc

    @staticmethod
    def _decode_tool_call(
        raw: Mapping[str, Any],
        request: IntelligenceRequest,
    ) -> IntelligenceToolProposal:
        if not isinstance(raw, Mapping):
            raise TypeError("tool_call must be an object")

        allowed = {
            "request_id",
            "task_id",
            "tool",
            "operation",
            "arguments",
        }
        forbidden = {
            "schema_version",
            "permissions",
            "timeout_ms",
            "retry_mode",
            "idempotency_key",
        }

        present = sorted(set(raw) & forbidden)
        if present:
            raise IntelligenceContractError(
                "model cannot supply authority fields: " + ", ".join(present)
            )

        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise IntelligenceContractError(
                "unknown tool proposal fields: " + ", ".join(unknown)
            )

        missing = sorted(allowed - set(raw))
        if missing:
            raise IntelligenceContractError(
                "missing tool proposal fields: " + ", ".join(missing)
            )

        request_id = UUID(str(raw["request_id"]))
        task_id = UUID(str(raw["task_id"]))

        if request_id != request.request_id or task_id != request.task_id:
            raise IntelligenceContractError(
                "tool proposal correlation IDs must match IntelligenceRequest"
            )

        arguments = raw["arguments"]
        if not isinstance(arguments, Mapping):
            raise TypeError("arguments must be an object")

        return IntelligenceToolProposal(
            request_id=request_id,
            task_id=task_id,
            tool=str(raw["tool"]),
            operation=str(raw["operation"]),
            arguments=dict(arguments),
        )
