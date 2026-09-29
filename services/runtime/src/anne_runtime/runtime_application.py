from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID, uuid4

from .audit import AppendOnlyAuditLog
from .contracts import (
    PermissionClass,
    PermissionDecision,
    PermissionScope,
    RetryMode,
    TaskRequest,
)
from .deterministic_provider import DeterministicModelProvider
from .execution import ExecutionCoordinator
from .gemini_provider import GeminiModelProvider
from .intelligence_contracts import IntelligenceRequest
from .intelligence_orchestrator import IntelligenceOrchestrator
from .intelligence_planning_loop import IntelligencePlanningLoop
from .intelligence_runtime_bridge import IntelligenceRuntimeBridge
from .intelligence_tool_authority import (
    ToolAuthorityResolver,
    ToolCapabilityCatalog,
)
from .model_router import ModelRouter
from .model_service import ModelService
from .calculator_tool import calculator_handler
from .orchestrator import TaskOrchestrator
from .policy import PolicyBroker, PolicyRule
from .provider_registry import ProviderRegistry
from .tool_contracts import (
    ToolArgument,
    ToolArgumentSchema,
    ToolDescriptor,
    ToolValueType,
)
from .tool_executor import ToolExecutor
from .tool_registry import ToolRegistry
from .tooling import AuthorizedToolRunner


INTELLIGENCE_CONTRACT_VERSION = "1.0"
MAX_USER_INTENT_LENGTH = 16_000
MAX_CONVERSATION_MESSAGES = 32
MAX_CONVERSATION_CONTENT_LENGTH = 16_000

MODEL_PROVIDER_ENV = "ANNE_MODEL_PROVIDER"
MODEL_NAME_ENV = "ANNE_MODEL_NAME"

DETERMINISTIC_PROVIDER_ID = "deterministic"
DETERMINISTIC_MODEL = "deterministic-v1"

GEMINI_PROVIDER_ID = "gemini"
GEMINI_MODEL = "gemini-3.5-flash-lite"


class RuntimeApplicationError(RuntimeError):
    """Raised when a runtime application request cannot be processed safely."""


class RuntimeApplication:
    """
    Runtime-owned composition root for the Ann-E intelligence application.

    The desktop/UI layer never constructs model providers, planners, tools,
    policies, or authority objects. All of those remain inside the runtime.

    The deterministic provider remains the default so the desktop/runtime
    integration remains offline and deterministic unless a different provider
    is explicitly selected through the runtime environment.

    Supported provider selection:

        ANNE_MODEL_PROVIDER=deterministic
        ANNE_MODEL_PROVIDER=gemini

    Optional model selection:

        ANNE_MODEL_NAME=<model>

    Gemini-specific model selection:

        ANNE_GEMINI_MODEL=<model>

    Model provider output remains untrusted model data and must pass through
    the existing Ann-E intelligence and runtime security boundaries.
    """

    def __init__(self, repository_root: Path) -> None:
        self._repository_root = repository_root.resolve()

        self._workspace_id = uuid4()

        self._schema_dir = (
            self._repository_root
            / "packages"
            / "schemas"
        )

        self._audit_path = (
            self._repository_root
            / "runtime-data"
            / "audit.jsonl"
        )

        self._audit_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not self._schema_dir.is_dir():
            raise RuntimeApplicationError(
                "Ann-E schema directory was not found: "
                f"{self._schema_dir}"
            )

        self._tool_registry = ToolRegistry()
        self._register_alpha_echo_tool()
        self._register_calculator_tool()

        self._policy = PolicyBroker(
            rules=[
                PolicyRule(
                    permission_class=PermissionClass.READ,
                    target_pattern="anne/runtime/alpha-echo",
                    decision=PermissionDecision.ALLOW,
                ),
            ],
        )

        self._tool_executor = ToolExecutor(
            self._tool_registry,
            self._policy,
        )

        self._authorized_runner = AuthorizedToolRunner(
            self._policy,
            self._tool_executor,
        )

        self._execution = ExecutionCoordinator(
            self._authorized_runner,
        )

        self._task_orchestrator = TaskOrchestrator(
            self._execution,
            AppendOnlyAuditLog(self._audit_path),
            self._schema_dir,
            default_timeout_ms=5_000,
        )

        self._authority_resolver = ToolAuthorityResolver(
            self._tool_registry,
        )

        self._capability_catalog = ToolCapabilityCatalog(
            self._tool_registry,
        )

        self._model_service = self._build_model_service()

        self._intelligence = IntelligenceOrchestrator(
            self._model_service,
            capability_catalog=self._capability_catalog,
        )

        self._runtime_bridge = IntelligenceRuntimeBridge(
            self._task_orchestrator,
            self._authority_resolver,
        )

        self._planning_loop = IntelligencePlanningLoop(
            self._intelligence,
            self._runtime_bridge,
            max_iterations=8,
        )

    def _register_calculator_tool(self) -> None:
        """Register the safe deterministic engineering calculator."""
        self._tool_registry.register(
            ToolDescriptor(
                tool_id="anne.calculator",
                version="1.0.0",
                description=(
                    "Safe deterministic arithmetic calculator for engineering "
                    "and numeric calculations."
                ),
                capabilities=("engineering.calculation",),
                arguments=ToolArgumentSchema(
                    arguments=(
                        ToolArgument(
                            name="expression",
                            value_type=ToolValueType.STRING,
                            required=True,
                            description="Arithmetic expression to evaluate safely.",
                        ),
                    )
                ),
                required_permissions=(),
                retry_mode=RetryMode.NONE,
                max_timeout_ms=1000,
            ),
            calculator_handler,
        )

    def _register_alpha_echo_tool(self) -> None:
        """Register the safe internal tool used to verify Phase 2 execution."""

        self._tool_registry.register(
            ToolDescriptor(
                tool_id="anne.echo",
                version="1.0.0",
                description=(
                    "Safe internal Alpha Core verification tool that "
                    "returns the supplied value unchanged."
                ),
                capabilities=("internal.echo",),
                arguments=ToolArgumentSchema(
                    arguments=(
                        ToolArgument(
                            name="value",
                            value_type=ToolValueType.STRING,
                            required=True,
                            description="Text value to echo unchanged.",
                        ),
                    ),
                ),
                required_permissions=(
                    PermissionScope(
                        PermissionClass.READ,
                        "anne/runtime/alpha-echo",
                    ),
                ),
                retry_mode=RetryMode.NONE,
                max_timeout_ms=1_000,
            ),
            self._alpha_echo_handler,
        )

    @staticmethod
    def _alpha_echo_handler(
        context: Any,
        arguments: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Return the supplied value without performing external side effects."""

        if context.is_cancelled():
            context.raise_if_cancelled()

        return {
            "echo": arguments["value"],
        }

    @property
    def workspace_id(self) -> UUID:
        """Return the runtime-owned workspace identity."""
        return self._workspace_id

    def handle_message(
        self,
        *,
        request_id: str,
        task_id: str,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        """
        Process one desktop conversation message through the real
        Phase 1 intelligence pipeline.
        """

        request_uuid = self._parse_uuid(
            request_id,
            "request_id",
        )

        task_uuid = self._parse_uuid(
            task_id,
            "task_id",
        )

        user_intent = self._parse_user_intent(payload)

        conversation = self._parse_conversation(
            payload.get("conversation"),
        )

        intelligence_request = IntelligenceRequest(
            request_id=request_uuid,
            task_id=task_uuid,
            user_intent=user_intent,
            conversation=conversation,
            metadata={
                "source": "desktop",
                "runtime_contract_version": INTELLIGENCE_CONTRACT_VERSION,
            },
        )

        task_request = TaskRequest(
            schema_version="1.0",
            request_id=request_uuid,
            task_id=task_uuid,
            created_at=self._utc_timestamp(),
            source="ui",
            user_intent=user_intent,
            priority="normal",
            workspace_id=self._workspace_id,
            requested_capabilities=(),
            approval_required=False,
            approval_id=None,
            input_artifacts=(),
        )

        outcome = self._planning_loop.run(
            intelligence_request,
            task_request,
        )

        if not outcome.completed:
            raise RuntimeApplicationError(
                "Intelligence planning did not produce a final response. "
                f"Stop reason: {outcome.stop_reason}"
            )

        last_iteration = outcome.iterations[-1]

        return {
            "response_text": outcome.final_response,
            "stop_reason": outcome.stop_reason,
            "iterations": len(outcome.iterations),
            "provider_id": last_iteration.invocation.provider_id,
            "provider_version": (
                last_iteration.invocation.provider_version
            ),
            "model": last_iteration.invocation.model,
        }

    def _build_model_service(self) -> ModelService:
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
                or os.getenv("ANNE_GEMINI_MODEL")
                or GEMINI_MODEL
            ).strip()

            if not gemini_model:
                raise RuntimeApplicationError(
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
                raise RuntimeApplicationError(
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

        raise RuntimeApplicationError(
            "Unsupported model provider: "
            f"{selected_provider}"
        )

    @staticmethod
    def _deterministic_responder(model_request: Any) -> str:
        """
        Produce valid IntelligenceDecision JSON for the first real
        desktop integration.

        This is intentionally deterministic and side-effect free.
        """

        if not model_request.messages:
            response_text = (
                "Ann-E received an empty conversation."
            )
        else:
            latest_message = model_request.messages[-1]

            response_text = (
                "I received your message through the Ann-E Phase 1 "
                "intelligence runtime:\n\n"
                f"{latest_message.content}\n\n"
                "The message successfully crossed the desktop runtime "
                "boundary, IntelligenceRequest, IntelligenceOrchestrator, "
                "ModelService, and IntelligencePlanningLoop."
            )

        return json.dumps(
            {
                "contract_version": INTELLIGENCE_CONTRACT_VERSION,
                "decision_type": "FINAL_RESPONSE",
                "response_text": response_text,
            }
        )

    @staticmethod
    def _parse_uuid(
        value: str,
        field_name: str,
    ) -> UUID:
        if not isinstance(value, str):
            raise RuntimeApplicationError(
                f"{field_name} must be a string."
            )

        try:
            return UUID(value)
        except ValueError as exc:
            raise RuntimeApplicationError(
                f"{field_name} must be a valid UUID."
            ) from exc

    @staticmethod
    def _parse_user_intent(
        payload: Mapping[str, Any],
    ) -> str:
        value = payload.get("user_intent")

        if not isinstance(value, str):
            raise RuntimeApplicationError(
                "message payload user_intent must be a string."
            )

        value = value.strip()

        if not value:
            raise RuntimeApplicationError(
                "message payload user_intent must not be blank."
            )

        if len(value) > MAX_USER_INTENT_LENGTH:
            raise RuntimeApplicationError(
                "message payload user_intent exceeds the maximum "
                f"length of {MAX_USER_INTENT_LENGTH} characters."
            )

        return value

    @staticmethod
    def _parse_conversation(
        raw_conversation: Any,
    ) -> tuple[Mapping[str, Any], ...]:
        if raw_conversation is None:
            return ()

        if not isinstance(raw_conversation, list):
            raise RuntimeApplicationError(
                "message payload conversation must be an array."
            )

        if len(raw_conversation) > MAX_CONVERSATION_MESSAGES:
            raise RuntimeApplicationError(
                "message payload conversation exceeds the maximum "
                f"of {MAX_CONVERSATION_MESSAGES} messages."
            )

        normalized: list[Mapping[str, Any]] = []

        for index, item in enumerate(raw_conversation):
            if not isinstance(item, Mapping):
                raise RuntimeApplicationError(
                    "conversation entry "
                    f"{index} must be an object."
                )

            role = item.get("role")
            content = item.get("content")

            if not isinstance(role, str) or not role.strip():
                raise RuntimeApplicationError(
                    f"conversation entry {index} has an invalid role."
                )

            if not isinstance(content, str):
                raise RuntimeApplicationError(
                    f"conversation entry {index} has invalid content."
                )

            content = content.strip()

            if not content:
                raise RuntimeApplicationError(
                    f"conversation entry {index} cannot be blank."
                )

            if len(content) > MAX_CONVERSATION_CONTENT_LENGTH:
                raise RuntimeApplicationError(
                    f"conversation entry {index} exceeds the maximum "
                    f"length of {MAX_CONVERSATION_CONTENT_LENGTH} "
                    "characters."
                )

            entry: dict[str, Any] = {
                "role": role.strip(),
                "content": content,
            }

            name = item.get("name")

            if name is not None:
                if not isinstance(name, str):
                    raise RuntimeApplicationError(
                        f"conversation entry {index} has an invalid name."
                    )

                entry["name"] = name

            normalized.append(entry)

        return tuple(normalized)

    @staticmethod
    def _utc_timestamp() -> str:
        return (
            datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
