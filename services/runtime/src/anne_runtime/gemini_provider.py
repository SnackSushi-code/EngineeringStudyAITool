from __future__ import annotations

import re
import json
import os
from typing import Any, Literal

from pydantic import BaseModel

from .model_contracts import (
    FinishReason,
    ModelCapability,
    ModelContractError,
    ModelProviderDescriptor,
    ModelProviderError,
    ModelRequest,
    ModelResponse,
    ModelUsage,
)


class GeminiToolCallSchema(BaseModel):
    """Gemini-safe representation of an untrusted tool proposal.

    Gemini Developer API structured output does not support arbitrary
    object schemas containing additionalProperties. Tool arguments are
    therefore represented as a JSON string at the provider boundary and
    converted back into the canonical Ann-E mapping after validation.
    """

    request_id: str
    task_id: str
    tool: str
    operation: str
    arguments_json: str


class GeminiDecisionSchema(BaseModel):
    """Gemini-safe representation of an Ann-E intelligence decision.

    This schema intentionally contains no runtime authority fields.
    Authority is created only after the model output crosses the
    Ann-E IntelligenceOrchestrator and RuntimeBridge boundaries.
    """

    contract_version: Literal["1.0"]
    decision_type: Literal[
        "FINAL_RESPONSE",
        "TOOL_PROPOSAL",
    ]
    response_text: str | None
    tool_call: GeminiToolCallSchema | None


class GeminiModelProvider:
    """Google Gemini provider for the Ann-E model-provider boundary.

    This provider performs model inference only.

    It does not:
    - execute tools,
    - construct permissions,
    - construct runtime authority,
    - modify policy,
    - access Ann-E protected resources.

    Gemini output remains untrusted model data and must pass through
    IntelligenceOrchestrator before becoming an Ann-E decision.
    """

    DEFAULT_PROVIDER_ID = "gemini"
    DEFAULT_PROVIDER_VERSION = "1.0.0"
    DEFAULT_MODEL = "gemini-3.5-flash-lite"
    DEFAULT_TIMEOUT_MS = 120_000

    RESPONSE_SCHEMA = GeminiDecisionSchema

    SYSTEM_INSTRUCTION = """
You are Ann-E, an engineering-focused AI assistant operating inside a
security-boundaried runtime.

Return exactly one structured Ann-E intelligence decision.

Rules:

1. contract_version must be "1.0".
2. decision_type must be either FINAL_RESPONSE or TOOL_PROPOSAL.
3. For FINAL_RESPONSE:
   - response_text contains the complete answer.
   - tool_call must be null.
4. For TOOL_PROPOSAL:
   - response_text must be null.
   - tool_call contains request_id, task_id, tool, operation, and
     arguments_json.
5. request_id and task_id must exactly match the identifiers supplied
   in the runtime context.
6. arguments_json must be a valid JSON object encoded as a string.
7. Never output runtime authority fields inside tool_call.
8. Never output:
   - permissions
   - timeout_ms
   - retry_mode
   - idempotency_key
   - schema_version
   - authorization
   - policy
9. Never claim that a tool was executed merely because you proposed it.
10. Never invent tool results.
11. If no tool is clearly required, return FINAL_RESPONSE.
12. Be precise and technically grounded.
13. For engineering problems, show relevant assumptions,
    equations, calculations, and reasoning.
14. Return JSON only.
""".strip()

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        provider_id: str = DEFAULT_PROVIDER_ID,
        provider_version: str = DEFAULT_PROVIDER_VERSION,
        client: Any | None = None,
        timeout_ms: int | None = None,
    ) -> None:
        if not provider_id.strip():
            raise ModelContractError(
                "provider_id cannot be blank"
            )

        if not provider_version.strip():
            raise ModelContractError(
                "provider_version cannot be blank"
            )

        resolved_model = (
            model
            or os.getenv("ANNE_GEMINI_MODEL")
            or self.DEFAULT_MODEL
        ).strip()

        if not resolved_model:
            raise ModelContractError(
                "Gemini model cannot be blank"
            )

        resolved_api_key = (
            api_key
            or os.getenv("ANNE_GEMINI_API_KEY")
            or os.getenv("GEMINI_API_KEY")
        )

        resolved_timeout = timeout_ms

        if resolved_timeout is None:
            timeout_env = os.getenv("ANNE_GEMINI_TIMEOUT_MS")

            if timeout_env is None:
                resolved_timeout = self.DEFAULT_TIMEOUT_MS
            else:
                try:
                    resolved_timeout = int(timeout_env)
                except ValueError as exc:
                    raise ModelContractError(
                        "ANNE_GEMINI_TIMEOUT_MS must be an integer"
                    ) from exc

        if resolved_timeout <= 0:
            raise ModelContractError(
                "Gemini timeout_ms must be greater than zero"
            )

        if client is None:
            if not resolved_api_key:
                raise ModelProviderError(
                    "Gemini API key is not configured.",
                    code="GEMINI_API_KEY_MISSING",
                    retryable=False,
                )

            try:
                from google import genai
            except ImportError as exc:
                raise ModelProviderError(
                    "The google-genai package is not installed.",
                    code="GEMINI_SDK_MISSING",
                    retryable=False,
                ) from exc

            try:
                client = genai.Client(
                    api_key=resolved_api_key
                )
            except Exception as exc:
                raise ModelProviderError(
                    "Failed to initialize the Gemini client.",
                    code="GEMINI_CLIENT_INITIALIZATION_FAILED",
                    retryable=False,
                ) from exc

        self._client = client
        self._model = resolved_model
        self._timeout_ms = resolved_timeout

        self._descriptor = ModelProviderDescriptor(
            provider_id=provider_id,
            provider_version=provider_version,
            models=(resolved_model,),
            capabilities=frozenset(
                {
                    ModelCapability.TEXT_INPUT,
                    ModelCapability.TEXT_OUTPUT,
                    ModelCapability.STRUCTURED_OUTPUT,
                }
            ),
        )

    @property
    def descriptor(self) -> ModelProviderDescriptor:
        return self._descriptor

    def generate(
        self,
        request: ModelRequest,
    ) -> ModelResponse:
        model = request.model

        if model is None:
            raise ModelContractError(
                "ModelRouter must resolve a model before provider invocation."
            )

        if model not in self._descriptor.models:
            raise ModelContractError(
                f"Unsupported Gemini model: {model}"
            )

        system_instruction, contents = self._build_contents(
            request
        )

        try:
            response = self._client.models.generate_content(
                model=model,
                contents=contents,
                config={
                    "system_instruction": system_instruction,
                    "temperature": request.generation.temperature,
                    "top_p": request.generation.top_p,
                    "max_output_tokens": (
                        request.generation.max_output_tokens
                    ),
                    "http_options": {
                        "timeout": self._timeout_ms,
                    },
                    "response_mime_type": "application/json",

                    # IMPORTANT:
                    # Use response_json_schema instead of response_schema.
                    #
                    # The Pydantic model contains nullable fields. The
                    # response_schema path in some google-genai SDK versions
                    # converts those into JSON Schema type arrays and then
                    # attempts to validate them as the narrower Gemini
                    # Schema type. response_json_schema accepts the actual
                    # JSON Schema produced by Pydantic.
                    "response_json_schema": (
                        self.RESPONSE_SCHEMA.model_json_schema()
                    ),
                },
            )
        except Exception as exc:
            raise self._provider_error(exc) from exc

        raw_content = self._extract_text(response)

        content = self._normalize_model_decision(
            raw_content,
            request,
        )

        return ModelResponse(
            request_id=request.request_id,
            task_id=request.task_id,
            provider_id=self._descriptor.provider_id,
            provider_version=self._descriptor.provider_version,
            model=model,
            content=content,
            finish_reason=self._extract_finish_reason(
                response
            ),
            usage=self._extract_usage(response),
            raw_metadata={
                "provider": "google-gemini",
                "structured_output": True,
                "arguments_encoding": "json_string",
            },
        )

    @classmethod
    def _normalize_model_decision(
        cls,
        raw_content: str,
        request: ModelRequest,
    ) -> str:
        try:
            decision = GeminiDecisionSchema.model_validate_json(
                raw_content
            )
        except Exception as exc:
            raise ModelProviderError(
                "Gemini returned structured output that does not match "
                "the Ann-E intelligence decision schema.",
                code="GEMINI_INVALID_STRUCTURED_OUTPUT",
                retryable=False,
            ) from exc

        if decision.contract_version != "1.0":
            raise ModelProviderError(
                "Gemini returned an unsupported Ann-E contract version.",
                code="GEMINI_UNSUPPORTED_CONTRACT_VERSION",
                retryable=False,
            )

        if decision.decision_type == "FINAL_RESPONSE":
            if decision.tool_call is not None:
                raise ModelProviderError(
                    "Gemini returned a tool call for FINAL_RESPONSE.",
                    code="GEMINI_INVALID_FINAL_RESPONSE",
                    retryable=False,
                )

            if decision.response_text is None:
                raise ModelProviderError(
                    "Gemini returned FINAL_RESPONSE without response_text.",
                    code="GEMINI_MISSING_RESPONSE_TEXT",
                    retryable=False,
                )

            canonical = {
                "contract_version": "1.0",
                "decision_type": "FINAL_RESPONSE",
                "response_text": decision.response_text,
                "tool_call": None,
            }

            return json.dumps(
                canonical,
                separators=(",", ":"),
            )

        if decision.response_text is not None:
            raise ModelProviderError(
                "Gemini returned response_text for TOOL_PROPOSAL.",
                code="GEMINI_INVALID_TOOL_PROPOSAL",
                retryable=False,
            )

        tool_call = decision.tool_call

        if tool_call is None:
            raise ModelProviderError(
                "Gemini returned TOOL_PROPOSAL without tool_call.",
                code="GEMINI_MISSING_TOOL_CALL",
                retryable=False,
            )

        expected_request_id = str(request.request_id)
        expected_task_id = str(request.task_id)

        if tool_call.request_id != expected_request_id:
            raise ModelProviderError(
                "Gemini returned a tool proposal for the wrong request_id.",
                code="GEMINI_REQUEST_ID_MISMATCH",
                retryable=False,
            )

        if tool_call.task_id != expected_task_id:
            raise ModelProviderError(
                "Gemini returned a tool proposal for the wrong task_id.",
                code="GEMINI_TASK_ID_MISMATCH",
                retryable=False,
            )

        if not tool_call.tool.strip():
            raise ModelProviderError(
                "Gemini returned a blank tool identifier.",
                code="GEMINI_INVALID_TOOL_ID",
                retryable=False,
            )

        if not tool_call.operation.strip():
            raise ModelProviderError(
                "Gemini returned a blank tool operation.",
                code="GEMINI_INVALID_OPERATION",
                retryable=False,
            )

        try:
            arguments = json.loads(
                tool_call.arguments_json
            )
        except (TypeError, json.JSONDecodeError) as exc:
            raise ModelProviderError(
                "Gemini returned invalid JSON in arguments_json.",
                code="GEMINI_INVALID_TOOL_ARGUMENTS_JSON",
                retryable=False,
            ) from exc

        if not isinstance(arguments, dict):
            raise ModelProviderError(
                "Gemini tool arguments must decode to a JSON object.",
                code="GEMINI_TOOL_ARGUMENTS_NOT_OBJECT",
                retryable=False,
            )

        canonical = {
            "contract_version": "1.0",
            "decision_type": "TOOL_PROPOSAL",
            "response_text": None,
            "tool_call": {
                "request_id": expected_request_id,
                "task_id": expected_task_id,
                "tool": tool_call.tool,
                "operation": tool_call.operation,
                "arguments": arguments,
            },
        }

        return json.dumps(
            canonical,
            separators=(",", ":"),
        )

    @classmethod
    def _build_contents(
        cls,
        request: ModelRequest,
    ) -> tuple[str, list[dict[str, Any]]]:
        contents: list[dict[str, Any]] = []

        runtime_context = (
            "\n\n"
            "Ann-E runtime context:\n"
            f"request_id={request.request_id}\n"
            f"task_id={request.task_id}\n"
        )

        tool_catalog = request.metadata.get("anne.tool_catalog")
        if tool_catalog:
            runtime_context += (
                "\n\n"
                "Ann-E available tools:\n"
                f"{tool_catalog}"
            )

        engineering_candidates = request.metadata.get(
            "anne.engineering_candidates"
        )
        if engineering_candidates:
            runtime_context += (
                "\n\n"
                "Ann-E engineering capability candidates:\n"
                f"{engineering_candidates}"
            )

        for message in request.messages:
            role = message.role.value

            if role == "system":
                continue

            if role == "assistant":
                gemini_role = "model"
            else:
                gemini_role = "user"

            content = message.content

            if role == "user":
                content = content + runtime_context

            contents.append(
                {
                    "role": gemini_role,
                    "parts": [
                        {
                            "text": content,
                        }
                    ],
                }
            )

        if not contents:
            raise ModelContractError(
                "Gemini request contains no usable messages."
            )

        return (
            cls.SYSTEM_INSTRUCTION,
            contents,
        )

    @staticmethod
    def _extract_text(
        response: Any,
    ) -> str:
        text = getattr(
            response,
            "text",
            None,
        )

        if not isinstance(text, str) or not text.strip():
            raise ModelProviderError(
                "Gemini returned an empty response.",
                code="GEMINI_EMPTY_RESPONSE",
                retryable=True,
            )

        return text.strip()

    @staticmethod
    def _extract_usage(
        response: Any,
    ) -> ModelUsage:
        usage = getattr(
            response,
            "usage_metadata",
            None,
        )

        if usage is None:
            return ModelUsage()

        input_tokens = getattr(
            usage,
            "prompt_token_count",
            None,
        )

        output_tokens = getattr(
            usage,
            "candidates_token_count",
            None,
        )

        total_tokens = getattr(
            usage,
            "total_token_count",
            None,
        )

        return ModelUsage(
            input_tokens=(
                input_tokens
                if isinstance(input_tokens, int)
                else None
            ),
            output_tokens=(
                output_tokens
                if isinstance(output_tokens, int)
                else None
            ),
            total_tokens=(
                total_tokens
                if isinstance(total_tokens, int)
                else None
            ),
        )

    @staticmethod
    def _extract_finish_reason(
        response: Any,
    ) -> FinishReason:
        candidates = getattr(
            response,
            "candidates",
            None,
        )

        if not candidates:
            return FinishReason.STOP

        reason = getattr(
            candidates[0],
            "finish_reason",
            None,
        )

        if reason is None:
            return FinishReason.STOP

        normalized = str(reason).upper()

        if "MAX_TOKENS" in normalized:
            return FinishReason.LENGTH

        if (
            "SAFETY" in normalized
            or "BLOCK" in normalized
        ):
            return FinishReason.CONTENT_FILTER

        return FinishReason.STOP

    @staticmethod
    def _provider_error(
        exc: Exception,
    ) -> ModelProviderError:
        # google-genai APIError exposes the HTTP response code as `code`.
        # Some other clients expose it as `status_code`.
        status_code = getattr(exc, "status_code", None)
        if not isinstance(status_code, int):
            status_code = getattr(exc, "code", None)

        if not isinstance(status_code, int):
            status_code = None

        # Keep only a short, machine-style status label. Do not include
        # raw exception text or response bodies in diagnostics.
        raw_status = getattr(exc, "status", None)
        safe_status = None
        if isinstance(raw_status, str):
            candidate = raw_status.strip()
            if candidate and len(candidate) <= 80 and re.fullmatch(
                r"[A-Za-z0-9_.-]+", candidate
            ):
                safe_status = candidate

        status_suffix = ""
        if status_code is not None:
            status_suffix = f" (HTTP {status_code}"
            if safe_status:
                status_suffix += f", status={safe_status}"
            status_suffix += ")"
        elif safe_status:
            status_suffix = f" (status={safe_status})"

        if status_code in (401, 403):
            return ModelProviderError(
                "Gemini authentication failed." + status_suffix,
                code="GEMINI_AUTHENTICATION_FAILED",
                retryable=False,
            )

        if status_code == 429:
            return ModelProviderError(
                "Gemini rate limit was reached." + status_suffix,
                code="GEMINI_RATE_LIMITED",
                retryable=True,
            )

        if status_code == 404:
            return ModelProviderError(
                "Gemini model or resource was not found." + status_suffix,
                code="GEMINI_RESOURCE_NOT_FOUND",
                retryable=False,
            )

        if status_code == 400:
            return ModelProviderError(
                "Gemini rejected the request as invalid." + status_suffix,
                code="GEMINI_INVALID_REQUEST",
                retryable=False,
            )

        if status_code == 408:
            return ModelProviderError(
                "Gemini request timed out." + status_suffix,
                code="GEMINI_TRANSPORT_ERROR",
                retryable=True,
            )

        if status_code == 409:
            return ModelProviderError(
                "Gemini reported a request conflict." + status_suffix,
                code="GEMINI_REQUEST_CONFLICT",
                retryable=False,
            )

        if status_code == 425:
            return ModelProviderError(
                "Gemini temporarily rejected the request." + status_suffix,
                code="GEMINI_TEMPORARILY_UNAVAILABLE",
                retryable=True,
            )

        if status_code == 408 or (
            status_code is not None and status_code >= 500
        ):
            return ModelProviderError(
                "Gemini service returned a server error." + status_suffix,
                code="GEMINI_SERVER_ERROR",
                retryable=True,
            )

        name = type(exc).__name__.lower()
        if any(
            marker in name
            for marker in ("timeout", "connection", "transport")
        ):
            return ModelProviderError(
                "Gemini transport request failed." + status_suffix,
                code="GEMINI_TRANSPORT_ERROR",
                retryable=True,
            )

        return ModelProviderError(
            f"Gemini request failed: {type(exc).__name__}" + status_suffix,
            code="GEMINI_REQUEST_FAILED",
            retryable=False,
        )
