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
from .engineering_capability_router import EngineeringCapabilityRouter
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
from .circuit_analysis_tool import circuit_analysis_handler
from .kinematics_tool import kinematics_handler
from .dynamics_tool import dynamics_handler
from .statics_tool import statics_handler
from .strength_of_materials_tool import strength_of_materials_handler
from .fluid_mechanics_tool import fluid_mechanics_handler
from .thermodynamics_tool import thermodynamics_handler
from .complex_math_tool import complex_math_handler
from .differential_equations_tool import differential_equations_handler
from .numerical_methods_tool import numerical_methods_handler
from .statistics_tool import statistics_handler
from .unit_conversion_tool import unit_conversion_handler
from .vector_math_tool import vector_math_handler
from .matrix_math_tool import matrix_math_handler
from .orchestrator import TaskOrchestrator
from .policy import PolicyBroker, PolicyRule
from .probability_tool import probability_handler
from .interpolation_tool import interpolation_handler
from .regression_tool import regression_handler
from .signal_processing_tool import frequency_domain_handler, signal_processing_handler
from .provider_registry import ProviderRegistry
from .tool_contracts import (
    ToolArgument,
    ToolArgumentSchema,
    ToolDescriptor,
    ToolExecutionType,
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
        self._register_unit_conversion_tool()
        self._register_vector_math_tool()
        self._register_matrix_math_tool()
        self._register_complex_math_tool()
        self._register_differential_equations_tool()
        self._register_numerical_methods_tool()
        self._register_statistics_tool()
        self._register_probability_tool()
        self._register_interpolation_tool()
        self._register_regression_tool()
        self._register_signal_processing_tool()
        self._register_circuit_analysis_tool()
        self._register_kinematics_tool()
        self._register_dynamics_tool()
        self._register_statics_tool()
        self._register_strength_of_materials_tool()
        self._register_fluid_mechanics_tool()
        self._register_thermodynamics_tool()

        self._policy = PolicyBroker(
            rules=[
                PolicyRule(
                    permission_class=PermissionClass.READ,
                    target_pattern="anne/runtime/alpha-echo",
                    decision=PermissionDecision.ALLOW,
                ),
                PolicyRule(
                    permission_class=PermissionClass.READ,
                    target_pattern="anne/runtime/probability",
                    decision=PermissionDecision.ALLOW,
                ),
                PolicyRule(
                    permission_class=PermissionClass.READ,
                    target_pattern="anne/runtime/interpolation",
                    decision=PermissionDecision.ALLOW,
                ),
                PolicyRule(
                    permission_class=PermissionClass.READ,
                    target_pattern="anne/runtime/regression",
                    decision=PermissionDecision.ALLOW,
                ),
                PolicyRule(
                    permission_class=PermissionClass.READ,
                    target_pattern="anne/runtime/signal-processing",
                    decision=PermissionDecision.ALLOW,
                ),
                PolicyRule(
                    permission_class=PermissionClass.READ,
                    target_pattern="anne/runtime/circuit-analysis",
                    decision=PermissionDecision.ALLOW,
                ),
                PolicyRule(
                    permission_class=PermissionClass.READ,
                    target_pattern="anne/runtime/kinematics",
                    decision=PermissionDecision.ALLOW,
                ),
                PolicyRule(
                    permission_class=PermissionClass.READ,
                    target_pattern="anne/runtime/dynamics",
                    decision=PermissionDecision.ALLOW,
                ),
                PolicyRule(
                    permission_class=PermissionClass.READ,
                    target_pattern="anne/runtime/statics",
                    decision=PermissionDecision.ALLOW,
                ),
                PolicyRule(
                    permission_class=PermissionClass.READ,
                    target_pattern="anne/runtime/strength_of_materials",
                    decision=PermissionDecision.ALLOW,
                ),
                PolicyRule(
                    permission_class=PermissionClass.READ,
                    target_pattern="anne/runtime/fluid_mechanics",
                    decision=PermissionDecision.ALLOW,
                ),
                PolicyRule(
                    permission_class=PermissionClass.READ,
                    target_pattern="anne/runtime/thermodynamics",
                    decision=PermissionDecision.ALLOW,
                ),
                PolicyRule(
                    permission_class=PermissionClass.READ,
                    target_pattern="anne/runtime/calculator",
                    decision=PermissionDecision.ALLOW,
                ),
                PolicyRule(
                    permission_class=PermissionClass.READ,
                    target_pattern="anne/runtime/unit-conversion",
                    decision=PermissionDecision.ALLOW,
                ),
                PolicyRule(
                    permission_class=PermissionClass.READ,
                    target_pattern="anne/runtime/vector-math",
                    decision=PermissionDecision.ALLOW,
                ),
                PolicyRule(
                    permission_class=PermissionClass.READ,
                    target_pattern="anne/runtime/matrix-math",
                    decision=PermissionDecision.ALLOW,
                ),
                PolicyRule(
                    permission_class=PermissionClass.READ,
                    target_pattern="anne/runtime/complex-math",
                    decision=PermissionDecision.ALLOW,
                ),
                PolicyRule(
                    permission_class=PermissionClass.READ,
                    target_pattern="anne/runtime/differential-equations",
                    decision=PermissionDecision.ALLOW,
                ),
        PolicyRule(
            permission_class=PermissionClass.READ,
            target_pattern="anne/runtime/statistics",
            decision=PermissionDecision.ALLOW,
        ),
                PolicyRule(
                    permission_class=PermissionClass.READ,
                    target_pattern="anne/runtime/numerical-methods",
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

        self._engineering_capability_router = EngineeringCapabilityRouter(
            self._capability_catalog.snapshot(),
        )

        self._model_service = self._build_model_service()

        self._intelligence = IntelligenceOrchestrator(
            self._model_service,
            capability_catalog=self._capability_catalog,
            engineering_router=self._engineering_capability_router,
        )

        self._runtime_bridge = IntelligenceRuntimeBridge(
            self._task_orchestrator,
            self._authority_resolver,
        )

        engineering_tool_ids = tuple(
            str(entry["tool_id"])
            for entry in self._capability_catalog.snapshot()
            if entry.get("engineering_domain") is not None
        )

        self._planning_loop = IntelligencePlanningLoop(
            self._intelligence,
            self._runtime_bridge,
            max_iterations=8,
            engineering_tool_ids=engineering_tool_ids,
        )

    def _register_unit_conversion_tool(self) -> None:
        """Register the safe deterministic engineering unit converter."""
        self._tool_registry.register(
            ToolDescriptor(
                tool_id="anne.unit_convert",
                version="1.0.0",
                description=(
                    "Safe deterministic engineering unit conversion across "
                    "compatible physical units."
                ),
                capabilities=("engineering.unit_conversion",),
                arguments=ToolArgumentSchema(
                    arguments=(
                        ToolArgument(
                            name="value",
                            value_type=ToolValueType.NUMBER,
                            required=True,
                            description="Numeric value to convert.",
                        ),
                        ToolArgument(
                            name="from_unit",
                            value_type=ToolValueType.STRING,
                            required=True,
                            description="Source engineering unit.",
                        ),
                        ToolArgument(
                            name="to_unit",
                            value_type=ToolValueType.STRING,
                            required=True,
                            description="Target engineering unit.",
                        ),
                    )
                ),
                required_permissions=(
                    PermissionScope(
                        PermissionClass.READ,
                        "anne/runtime/unit-conversion",
                    ),
                ),
                retry_mode=RetryMode.NONE,
                max_timeout_ms=1000,
            ),
            unit_conversion_handler,
        )

    def _register_vector_math_tool(self) -> None:
        """Register the safe deterministic engineering vector-math tool."""
        self._tool_registry.register(
            ToolDescriptor(
                tool_id="anne.vector_math",
                version="1.0.0",
                description=(
                    "Safe deterministic vector mathematics for engineering "
                    "calculations, including magnitude, addition, subtraction, "
                    "scaling, dot products, cross products, normalization, "
                    "and angles."
                ),
                capabilities=("engineering.vector_math",),
                arguments=ToolArgumentSchema(
                    arguments=(
                        ToolArgument(
                            name="operation",
                            value_type=ToolValueType.STRING,
                            required=True,
                            description="Vector-math operation to perform.",
                        ),
                        ToolArgument(
                            name="vector",
                            value_type=ToolValueType.ARRAY,
                            required=False,
                            description="Single numeric vector for unary operations.",
                        ),
                        ToolArgument(
                            name="left",
                            value_type=ToolValueType.ARRAY,
                            required=False,
                            description="Left numeric vector for binary operations.",
                        ),
                        ToolArgument(
                            name="right",
                            value_type=ToolValueType.ARRAY,
                            required=False,
                            description="Right numeric vector for binary operations.",
                        ),
                        ToolArgument(
                            name="scalar",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Numeric scalar for vector scaling.",
                        ),
                    )
                ),
                required_permissions=(
                    PermissionScope(
                        PermissionClass.READ,
                        "anne/runtime/vector-math",
                    ),
                ),
                retry_mode=RetryMode.NONE,
                max_timeout_ms=1000,
            ),
            vector_math_handler,
        )

    def _register_matrix_math_tool(self) -> None:
        """Register the safe deterministic engineering matrix-math tool."""
        self._tool_registry.register(
            ToolDescriptor(
                tool_id="anne.matrix_math",
                version="1.0.0",
                description=(
                    "Safe deterministic matrix mathematics for engineering "
                    "calculations, including matrix arithmetic, multiplication, "
                    "transposition, determinants, inverses, and matrix-vector products."
                ),
                capabilities=("engineering.matrix_math",),
                arguments=ToolArgumentSchema(
                    arguments=(
                        ToolArgument(
                            name="operation",
                            value_type=ToolValueType.STRING,
                            required=True,
                            description="Matrix-math operation to perform.",
                        ),
                        ToolArgument(
                            name="matrix",
                            value_type=ToolValueType.ARRAY,
                            required=False,
                            description="Single numeric matrix for unary operations.",
                        ),
                        ToolArgument(
                            name="left",
                            value_type=ToolValueType.ARRAY,
                            required=False,
                            description="Left numeric matrix for binary operations.",
                        ),
                        ToolArgument(
                            name="right",
                            value_type=ToolValueType.ARRAY,
                            required=False,
                            description="Right numeric matrix for binary operations.",
                        ),
                        ToolArgument(
                            name="vector",
                            value_type=ToolValueType.ARRAY,
                            required=False,
                            description="Numeric vector for matrix-vector multiplication.",
                        ),
                        ToolArgument(
                            name="scalar",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Numeric scalar for matrix scaling.",
                        ),
                        ToolArgument(
                            name="size",
                            value_type=ToolValueType.INTEGER,
                            required=False,
                            description="Positive matrix size for identity matrices.",
                        ),
                    )
                ),
                required_permissions=(
                    PermissionScope(
                        PermissionClass.READ,
                        "anne/runtime/matrix-math",
                    ),
                ),
                retry_mode=RetryMode.NONE,
                max_timeout_ms=1000,
            ),
            matrix_math_handler,
        )
    def _register_differential_equations_tool(self) -> None:
        """Register the safe deterministic engineering ODE solver."""
        self._tool_registry.register(
            ToolDescriptor(
                tool_id="anne.differential_equations",
                version="1.0.0",
                description=(
                    "Safe deterministic numerical solution of first-order "
                    "ordinary differential equations using Euler and RK4 "
                    "methods for initial-value problems."
                ),
                capabilities=("engineering.differential_equations",),
                arguments=ToolArgumentSchema(
                    arguments=(
                        ToolArgument(
                            name="operation",
                            value_type=ToolValueType.STRING,
                            required=True,
                            description=(
                                "Numerical integration method: euler or rk4."
                            ),
                        ),
                        ToolArgument(
                            name="expression",
                            value_type=ToolValueType.STRING,
                            required=True,
                            description=(
                                "Safe derivative expression f(t,y)."
                            ),
                        ),
                        ToolArgument(
                            name="t0",
                            value_type=ToolValueType.NUMBER,
                            required=True,
                            description="Initial independent-variable value.",
                        ),
                        ToolArgument(
                            name="y0",
                            value_type=ToolValueType.NUMBER,
                            required=True,
                            description="Initial dependent-variable value.",
                        ),
                        ToolArgument(
                            name="tf",
                            value_type=ToolValueType.NUMBER,
                            required=True,
                            description="Final independent-variable value.",
                        ),
                        ToolArgument(
                            name="step_size",
                            value_type=ToolValueType.NUMBER,
                            required=True,
                            description="Positive numerical integration step size.",
                        ),
                    )
                ),
                required_permissions=(
                    PermissionScope(
                        PermissionClass.READ,
                        "anne/runtime/differential-equations",
                    ),
                ),
                retry_mode=RetryMode.NONE,
                max_timeout_ms=1000,
            ),
            differential_equations_handler,
        )

    def _register_complex_math_tool(self) -> None:
        """Register the safe deterministic engineering complex-math tool."""
        self._tool_registry.register(
            ToolDescriptor(
                tool_id="anne.complex_math",
                version="1.0.0",
                description=(
                    "Safe deterministic complex-number mathematics for "
                    "engineering calculations, including arithmetic, "
                    "magnitude, phase, conjugates, components, and "
                    "rectangular-polar conversions."
                ),
                capabilities=("engineering.complex_math",),
                arguments=ToolArgumentSchema(
                    arguments=(
                        ToolArgument(
                            name="operation",
                            value_type=ToolValueType.STRING,
                            required=True,
                            description="Complex-math operation to perform.",
                        ),
                        ToolArgument(
                            name="value",
                            value_type=ToolValueType.OBJECT,
                            required=False,
                            description=(
                                "Complex value for unary operations, represented "
                                "by real and imaginary components."
                            ),
                        ),
                        ToolArgument(
                            name="left",
                            value_type=ToolValueType.OBJECT,
                            required=False,
                            description=(
                                "Left complex value for binary operations."
                            ),
                        ),
                        ToolArgument(
                            name="right",
                            value_type=ToolValueType.OBJECT,
                            required=False,
                            description=(
                                "Right complex value for binary operations."
                            ),
                        ),
                        ToolArgument(
                            name="magnitude",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Magnitude for polar conversion.",
                        ),
                        ToolArgument(
                            name="phase",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Phase in radians for polar conversion.",
                        ),
                    )
                ),
                required_permissions=(
                    PermissionScope(
                        PermissionClass.READ,
                        "anne/runtime/complex-math",
                    ),
                ),
                retry_mode=RetryMode.NONE,
                max_timeout_ms=1000,
            ),
            complex_math_handler,
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
                required_permissions=(
                    PermissionScope(
                        PermissionClass.READ,
                        "anne/runtime/calculator",
                    ),
                ),
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

    def _register_probability_tool(self) -> None:
        """Register the safe deterministic engineering probability tool."""
        self._tool_registry.register(
            ToolDescriptor(
                tool_id="anne.probability",
                version="1.0.0",
                description=(
                    "Safe deterministic probability calculations for "
                    "engineering and statistics, including binomial "
                    "probability and normal PDF/CDF calculations."
                ),
                capabilities=("engineering.probability",),
                arguments=ToolArgumentSchema(
                    arguments=(
                        ToolArgument(
                            name="operation",
                            value_type=ToolValueType.STRING,
                            required=True,
                            description=(
                                "Probability operation: binomial, "
                                "normal_pdf, or normal_cdf."
                            ),
                        ),
                        ToolArgument(
                            name="n",
                            value_type=ToolValueType.INTEGER,
                            required=False,
                            description="Number of binomial trials.",
                        ),
                        ToolArgument(
                            name="k",
                            value_type=ToolValueType.INTEGER,
                            required=False,
                            description="Number of binomial successes.",
                        ),
                        ToolArgument(
                            name="p",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Binomial success probability.",
                        ),
                        ToolArgument(
                            name="x",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Normal-distribution evaluation point.",
                        ),
                        ToolArgument(
                            name="mean",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Normal-distribution mean.",
                        ),
                        ToolArgument(
                            name="stddev",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Normal-distribution standard deviation.",
                        ),
                    )
                ),
                required_permissions=(
                    PermissionScope(
                        PermissionClass.READ,
                        "anne/runtime/probability",
                    ),
                ),
                retry_mode=RetryMode.NONE,
                max_timeout_ms=1000,
            ),
            probability_handler,
        )

    def _register_interpolation_tool(self) -> None:
        """Register the safe deterministic engineering interpolation tool."""
        self._tool_registry.register(
            ToolDescriptor(
                tool_id="anne.interpolation",
                version="1.0.0",
                description=(
                    "Safe deterministic interpolation for engineering and "
                    "scientific data using linear, Lagrange, Newton divided "
                    "difference, and natural cubic spline methods."
                ),
                capabilities=("engineering.interpolation",),
                arguments=ToolArgumentSchema(
                    arguments=(
                        ToolArgument(
                            name="operation",
                            value_type=ToolValueType.STRING,
                            required=True,
                            description=(
                                "Interpolation operation: linear, lagrange, "
                                "newton, or cubic_spline."
                            ),
                        ),
                        ToolArgument(
                            name="x_values",
                            value_type=ToolValueType.ARRAY,
                            required=True,
                            description="Known x-coordinate dataset.",
                        ),
                        ToolArgument(
                            name="y_values",
                            value_type=ToolValueType.ARRAY,
                            required=True,
                            description="Known y-coordinate dataset.",
                        ),
                        ToolArgument(
                            name="x",
                            value_type=ToolValueType.NUMBER,
                            required=True,
                            description="Target x-coordinate to interpolate.",
                        ),
                    )
                ),
                required_permissions=(
                    PermissionScope(
                        PermissionClass.READ,
                        "anne/runtime/interpolation",
                    ),
                ),
                retry_mode=RetryMode.NONE,
                max_timeout_ms=1000,
            ),
            interpolation_handler,
        )

    def _register_regression_tool(self) -> None:
        """Register the safe deterministic engineering regression tool."""
        self._tool_registry.register(
            ToolDescriptor(
                tool_id="anne.regression",
                version="1.0.0",
                description=(
                    "Safe deterministic regression for engineering and "
                    "scientific data, including linear regression, "
                    "correlation, and linear prediction."
                ),
                capabilities=("engineering.regression",),
                arguments=ToolArgumentSchema(
                    arguments=(
                        ToolArgument(
                            name="operation",
                            value_type=ToolValueType.STRING,
                            required=True,
                            description=(
                                "Regression operation: linear, correlation, "
                                "or predict."
                            ),
                        ),
                        ToolArgument(
                            name="x_values",
                            value_type=ToolValueType.ARRAY,
                            required=True,
                            description="Independent-variable dataset.",
                        ),
                        ToolArgument(
                            name="y_values",
                            value_type=ToolValueType.ARRAY,
                            required=True,
                            description="Dependent-variable dataset.",
                        ),
                        ToolArgument(
                            name="x",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Prediction x-coordinate.",
                        ),
                    )
                ),
                required_permissions=(
                    PermissionScope(
                        PermissionClass.READ,
                        "anne/runtime/regression",
                    ),
                ),
                retry_mode=RetryMode.NONE,
                max_timeout_ms=1000,
            ),
            regression_handler,
        )


    def _register_numerical_methods_tool(self) -> None:
        """Register safe deterministic numerical engineering methods."""
        self._tool_registry.register(
            ToolDescriptor(
                tool_id="anne.numerical_methods",
                version="1.0.0",
                description=(
                    "Safe deterministic numerical methods for engineering "
                    "calculations, including root finding, numerical "
                    "integration, and finite differences."
                ),
                capabilities=("engineering.numerical_methods",),
                arguments=ToolArgumentSchema(
                    arguments=(
                        ToolArgument(
                            name="operation",
                            value_type=ToolValueType.STRING,
                            required=True,
                            description=(
                                "Numerical method operation: bisection, brent, "
                                "newton, secant, trapezoidal, simpson, "
                                "forward_difference, central_difference, "
                                "or backward_difference."
                            ),
                        ),
                        ToolArgument(
                            name="expression",
                            value_type=ToolValueType.STRING,
                            required=True,
                            description="Safe mathematical expression.",
                        ),
                        ToolArgument(
                            name="lower",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Lower bound for root finding or integration.",
                        ),
                        ToolArgument(
                            name="upper",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Upper bound for root finding or integration.",
                        ),
                        ToolArgument(
                            name="initial_guess",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Initial guess for Newton or secant methods.",
                        ),
                        ToolArgument(
                            name="second_guess",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Second initial guess for the secant method.",
                        ),
                        ToolArgument(
                            name="tolerance",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Numerical convergence tolerance.",
                        ),
                        ToolArgument(
                            name="max_iterations",
                            value_type=ToolValueType.INTEGER,
                            required=False,
                            description="Maximum number of root-finding iterations.",
                        ),
                        ToolArgument(
                            name="steps",
                            value_type=ToolValueType.INTEGER,
                            required=False,
                            description="Number of numerical integration steps.",
                        ),
                        ToolArgument(
                            name="x",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Evaluation point for finite differences.",
                        ),
                        ToolArgument(
                            name="step_size",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Positive finite-difference step size.",
                        ),
                    )
                ),
                required_permissions=(
                    PermissionScope(
                        PermissionClass.READ,
                        "anne/runtime/numerical-methods",
                    ),
                ),
                retry_mode=RetryMode.NONE,
                max_timeout_ms=1000,
            ),
            numerical_methods_handler,
        )
    def _register_signal_processing_tool(self) -> None:
        """Register the safe deterministic engineering signal-processing tool."""
        self._tool_registry.register(
            ToolDescriptor(
                tool_id="anne.signal_processing",
                version="1.1.0",
                description=(
                    "Safe deterministic signal processing for engineering "
                    "data, including moving averages, RMS, peak analysis, "
                    "peak-to-peak measurements, discrete differences, "
                    "convolution, DFT, FFT, and magnitude-spectrum analysis."
                ),
                capabilities=("engineering.signal_processing",),
                arguments=ToolArgumentSchema(
                    arguments=(
                        ToolArgument(
                            name="operation",
                            value_type=ToolValueType.STRING,
                            required=True,
                            description=(
                                "Signal-processing operation: moving_average, "
                                "rms, peak, peak_to_peak, difference, "
                                "convolution, dft, fft, or magnitude_spectrum."
                            ),
                        ),
                        ToolArgument(
                            name="values",
                            value_type=ToolValueType.ARRAY,
                            required=True,
                            description="Numeric signal samples.",
                        ),
                        ToolArgument(
                            name="window",
                            value_type=ToolValueType.INTEGER,
                            required=False,
                            description="Moving-average window length.",
                        ),
                        ToolArgument(
                            name="kernel",
                            value_type=ToolValueType.ARRAY,
                            required=False,
                            description="Numeric convolution kernel.",
                        ),
                        ToolArgument(
                            name="sample_rate",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description=(
                                "Positive finite sample rate for "
                                "magnitude-spectrum analysis."
                            ),
                        ),
                    )
                ),
                required_permissions=(
                    PermissionScope(
                        PermissionClass.READ,
                        "anne/runtime/signal-processing",
                    ),
                ),
                retry_mode=RetryMode.NONE,
                max_timeout_ms=1000,
            ),
            signal_processing_handler,
        )

        self._tool_registry.register(
            ToolDescriptor(
                tool_id="anne.signal_processing.frequency_domain",
                version="1.0.0",
                description=(
                    "Safe deterministic frequency-domain signal processing "
                    "for engineering data using DFT, FFT, and magnitude "
                    "spectrum analysis."
                ),
                capabilities=("engineering.signal_processing.frequency_domain",),
                arguments=ToolArgumentSchema(
                    arguments=(
                        ToolArgument(
                            name="operation",
                            value_type=ToolValueType.STRING,
                            required=True,
                            description=(
                                "Frequency-domain operation: dft, fft, "
                                "or magnitude_spectrum."
                            ),
                        ),
                        ToolArgument(
                            name="values",
                            value_type=ToolValueType.ARRAY,
                            required=True,
                            description="Numeric signal samples.",
                        ),
                        ToolArgument(
                            name="sample_rate",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description=(
                                "Positive finite sample rate required for "
                                "magnitude-spectrum analysis."
                            ),
                        ),
                    ),
                ),
                required_permissions=(
                    PermissionScope(
                        PermissionClass.READ,
                        "anne/runtime/signal-processing",
                    ),
                ),
                retry_mode=RetryMode.NONE,
                max_timeout_ms=1000,
            ),
            frequency_domain_handler,
        )

    def _register_circuit_analysis_tool(self) -> None:
        """Register the safe deterministic engineering circuit-analysis tool."""
        self._tool_registry.register(
            ToolDescriptor(
                tool_id="anne.circuit_analysis",
                version="1.0.0",
                description=(
                    "Safe deterministic circuit analysis including Ohm's law, "
                    "series and parallel resistance, voltage and current "
                    "dividers, power, energy, and RC/RL time constants."
                ),
                capabilities=("engineering.circuit_analysis",),
                arguments=ToolArgumentSchema(
                    arguments=(
                        ToolArgument(
                            name="operation",
                            value_type=ToolValueType.STRING,
                            required=True,
                            description=(
                                "Circuit-analysis operation: ohms_law, "
                                "series_resistance, parallel_resistance, "
                                "voltage_divider, current_divider, power, "
                                "energy, rc_time_constant, or "
                                "rl_time_constant."
                            ),
                        ),
                        ToolArgument(
                            name="voltage",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Voltage in volts.",
                        ),
                        ToolArgument(
                            name="current",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Current in amperes.",
                        ),
                        ToolArgument(
                            name="resistance",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Resistance in ohms.",
                        ),
                        ToolArgument(
                            name="resistances",
                            value_type=ToolValueType.ARRAY,
                            required=False,
                            description="List of positive resistances in ohms.",
                        ),
                        ToolArgument(
                            name="input_voltage",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Divider input voltage in volts.",
                        ),
                        ToolArgument(
                            name="r1",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="First divider resistance in ohms.",
                        ),
                        ToolArgument(
                            name="r2",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Second divider resistance in ohms.",
                        ),
                        ToolArgument(
                            name="total_current",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Total divider current in amperes.",
                        ),
                        ToolArgument(
                            name="power",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Power in watts.",
                        ),
                        ToolArgument(
                            name="time_seconds",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Elapsed time in seconds.",
                        ),
                        ToolArgument(
                            name="resistance_ohms",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Resistance in ohms for time constants.",
                        ),
                        ToolArgument(
                            name="capacitance_farads",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Capacitance in farads.",
                        ),
                        ToolArgument(
                            name="inductance_henries",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Inductance in henries.",
                        ),
                    )
                ),
                required_permissions=(
                    PermissionScope(
                        PermissionClass.READ,
                        "anne/runtime/circuit-analysis",
                    ),
                ),
                retry_mode=RetryMode.NONE,
                max_timeout_ms=1000,
            ),
            circuit_analysis_handler,
        )

    def _register_kinematics_tool(self) -> None:
        """Register the safe deterministic engineering kinematics tool."""
        self._tool_registry.register(
            ToolDescriptor(
                tool_id="anne.kinematics",
                version="1.0.0",
                description=(
                    "Safe deterministic engineering kinematics for "
                    "velocity, displacement, acceleration, time, and "
                    "projectile-motion calculations."
                ),
                capabilities=("engineering.kinematics",),
                arguments=ToolArgumentSchema(
                    arguments=(
                        ToolArgument(
                            name="operation",
                            value_type=ToolValueType.STRING,
                            required=True,
                            description=(
                                "Kinematics operation: velocity, displacement, "
                                "final_velocity_from_displacement, acceleration, "
                                "time_from_velocity, projectile_time, "
                                "projectile_range, or projectile_max_height."
                            ),
                        ),
                        ToolArgument(
                            name="initial_velocity",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Initial velocity in m/s.",
                        ),
                        ToolArgument(
                            name="final_velocity",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Final velocity in m/s.",
                        ),
                        ToolArgument(
                            name="acceleration",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Acceleration in m/s^2.",
                        ),
                        ToolArgument(
                            name="time",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Elapsed time in seconds.",
                        ),
                        ToolArgument(
                            name="displacement",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Displacement in meters.",
                        ),
                        ToolArgument(
                            name="initial_speed",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Initial projectile speed in m/s.",
                        ),
                        ToolArgument(
                            name="launch_angle_degrees",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Projectile launch angle in degrees.",
                        ),
                        ToolArgument(
                            name="gravity",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description=(
                                "Positive gravitational acceleration in m/s^2. "
                                "Defaults to standard gravity."
                            ),
                        ),
                    ),
                ),
                engineering_domain="mechanical",
                execution_type=ToolExecutionType.NATIVE,
                required_software=(),
                input_artifact_types=("motion_specification",),
                output_artifact_types=("calculation_result",),
                required_permissions=(
                    PermissionScope(
                        PermissionClass.READ,
                        "anne/runtime/kinematics",
                    ),
                ),
                retry_mode=RetryMode.NONE,
                max_timeout_ms=1000,
            ),
            kinematics_handler,
        )

    def _register_dynamics_tool(self) -> None:
        """Register the safe deterministic engineering dynamics tool."""
        self._tool_registry.register(
            ToolDescriptor(
                tool_id="anne.dynamics",
                version="1.0.0",
                description=(
                    "Safe deterministic engineering dynamics for force, mass, "
                    "acceleration, weight, momentum, energy, work, and power "
                    "calculations."
                ),
                capabilities=("engineering.dynamics",),
                arguments=ToolArgumentSchema(
                    arguments=(
                        ToolArgument(
                            name="operation",
                            value_type=ToolValueType.STRING,
                            required=True,
                            description=(
                                "Dynamics operation: force, mass_from_force, "
                                "acceleration_from_force, weight, momentum, "
                                "kinetic_energy, potential_energy, work, or power."
                            ),
                        ),
                        ToolArgument(
                            name="mass",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Mass in kilograms.",
                        ),
                        ToolArgument(
                            name="acceleration",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Acceleration in m/s^2.",
                        ),
                        ToolArgument(
                            name="force",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Force in newtons.",
                        ),
                        ToolArgument(
                            name="gravity",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Positive gravitational acceleration in m/s^2.",
                        ),
                        ToolArgument(
                            name="velocity",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Velocity in m/s.",
                        ),
                        ToolArgument(
                            name="height",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Height in meters.",
                        ),
                        ToolArgument(
                            name="displacement",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Displacement in meters.",
                        ),
                        ToolArgument(
                            name="angle_degrees",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Work angle in degrees from 0 through 180.",
                        ),
                        ToolArgument(
                            name="work",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Work in joules.",
                        ),
                        ToolArgument(
                            name="time",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Time in seconds.",
                        ),
                    ),
                ),
                engineering_domain="mechanical",
                execution_type=ToolExecutionType.NATIVE,
                required_software=(),
                input_artifact_types=("dynamics_specification",),
                output_artifact_types=("calculation_result",),
                required_permissions=(
                    PermissionScope(
                        PermissionClass.READ,
                        "anne/runtime/dynamics",
                    ),
                ),
                retry_mode=RetryMode.NONE,
                max_timeout_ms=1000,
            ),
            dynamics_handler,
        )

    def _register_statics_tool(self) -> None:
        """Register the safe deterministic engineering statics tool."""
        self._tool_registry.register(
            ToolDescriptor(
                tool_id="anne.statics",
                version="1.0.0",
                description=(
                    "Safe deterministic engineering statics for force "
                    "components, resultant forces, moments, and equilibrium "
                    "calculations."
                ),
                capabilities=("engineering.statics",),
                arguments=ToolArgumentSchema(
                    arguments=(
                        ToolArgument(
                            name="operation",
                            value_type=ToolValueType.STRING,
                            required=True,
                            description=(
                                "Statics operation: force_components, "
                                "resultant_force, resultant_angle, "
                                "moment_2d, moment_from_force, "
                                "equilibrium_force, or equilibrium_check."
                            ),
                        ),
                        ToolArgument(
                            name="magnitude",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Force magnitude.",
                        ),
                        ToolArgument(
                            name="angle_degrees",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Force angle in degrees.",
                        ),
                        ToolArgument(
                            name="fx",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Force x-component.",
                        ),
                        ToolArgument(
                            name="fy",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Force y-component.",
                        ),
                        ToolArgument(
                            name="x",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Position x-coordinate.",
                        ),
                        ToolArgument(
                            name="y",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Position y-coordinate.",
                        ),
                        ToolArgument(
                            name="force",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Force magnitude.",
                        ),
                        ToolArgument(
                            name="perpendicular_distance",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Perpendicular distance from the moment center.",
                        ),
                        ToolArgument(
                            name="fx_sum",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Sum of force x-components.",
                        ),
                        ToolArgument(
                            name="fy_sum",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Sum of force y-components.",
                        ),
                        ToolArgument(
                            name="moment_sum",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Sum of moments.",
                        ),
                    )
                ),
                engineering_domain="mechanical",
                execution_type=ToolExecutionType.NATIVE,
                required_software=(),
                input_artifact_types=("statics_specification",),
                output_artifact_types=("calculation_result",),
                required_permissions=(
                    PermissionScope(
                        PermissionClass.READ,
                        "anne/runtime/statics",
                    ),
                ),
                retry_mode=RetryMode.NONE,
                max_timeout_ms=1000,
            ),
            statics_handler,
        )

    def _register_fluid_mechanics_tool(self) -> None:
        """Register the safe deterministic engineering fluid mechanics tool."""
        self._tool_registry.register(
            ToolDescriptor(
                tool_id="anne.fluid_mechanics",
                version="1.0.0",
                description=(
                    "Safe deterministic engineering fluid mechanics "
                    "calculations for pressure, hydrostatics, flow, "
                    "Reynolds number, Bernoulli analysis, buoyancy, "
                    "and hydraulic power."
                ),
                capabilities=("engineering.fluid_mechanics",),
                arguments=ToolArgumentSchema(
                    arguments=(
                        ToolArgument(
                            name="operation",
                            value_type=ToolValueType.STRING,
                            required=True,
                            description=(
                                "Fluid mechanics operation: pressure, "
                                "hydrostatic_pressure, absolute_pressure, "
                                "gauge_pressure, density, specific_weight, "
                                "continuity, volumetric_flow_rate, "
                                "mass_flow_rate, dynamic_pressure, "
                                "reynolds_number, hydraulic_power, "
                                "buoyant_force, or bernoulli_velocity."
                            ),
                        ),
                        ToolArgument(
                            name="force",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Applied force.",
                        ),
                        ToolArgument(
                            name="area",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Cross-sectional area.",
                        ),
                        ToolArgument(
                            name="density",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Fluid density.",
                        ),
                        ToolArgument(
                            name="gravity",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Gravitational acceleration.",
                        ),
                        ToolArgument(
                            name="depth",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Fluid depth.",
                        ),
                        ToolArgument(
                            name="gauge_pressure",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Gauge pressure.",
                        ),
                        ToolArgument(
                            name="atmospheric_pressure",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Atmospheric pressure.",
                        ),
                        ToolArgument(
                            name="absolute_pressure",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Absolute pressure.",
                        ),
                        ToolArgument(
                            name="mass",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Mass.",
                        ),
                        ToolArgument(
                            name="volume",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Volume.",
                        ),
                        ToolArgument(
                            name="area_1",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Upstream cross-sectional area.",
                        ),
                        ToolArgument(
                            name="velocity_1",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Upstream velocity.",
                        ),
                        ToolArgument(
                            name="area_2",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Downstream cross-sectional area.",
                        ),
                        ToolArgument(
                            name="velocity",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Fluid velocity.",
                        ),
                        ToolArgument(
                            name="volumetric_flow_rate",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Volumetric flow rate.",
                        ),
                        ToolArgument(
                            name="characteristic_length",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Characteristic length.",
                        ),
                        ToolArgument(
                            name="dynamic_viscosity",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Dynamic viscosity.",
                        ),
                        ToolArgument(
                            name="head",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Hydraulic head.",
                        ),
                        ToolArgument(
                            name="displaced_volume",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Displaced fluid volume.",
                        ),
                        ToolArgument(
                            name="pressure_1",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Pressure at point 1.",
                        ),
                        ToolArgument(
                            name="pressure_2",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Pressure at point 2.",
                        ),
                        ToolArgument(
                            name="elevation_1",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Elevation at point 1.",
                        ),
                        ToolArgument(
                            name="elevation_2",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Elevation at point 2.",
                        ),
                    )
                ),
                engineering_domain="mechanical",
                execution_type=ToolExecutionType.NATIVE,
                required_software=(),
                input_artifact_types=("fluid_mechanics_specification",),
                output_artifact_types=("calculation_result",),
                required_permissions=(
                    PermissionScope(
                        PermissionClass.READ,
                        "anne/runtime/fluid_mechanics",
                    ),
                ),
                retry_mode=RetryMode.NONE,
                max_timeout_ms=1000,
            ),
            fluid_mechanics_handler,
        )
    def _register_thermodynamics_tool(self) -> None:
        """Register the safe deterministic engineering thermodynamics tool."""
        self._tool_registry.register(
            ToolDescriptor(
                tool_id="anne.thermodynamics",
                version="1.0.0",
                description=(
                    "Safe deterministic engineering thermodynamics "
                    "calculations for ideal gases, heat transfer, "
                    "specific heat, latent heat, thermal efficiency, "
                    "refrigeration, heat pumps, the first law, and entropy."
                ),
                capabilities=("engineering.thermodynamics",),
                arguments=ToolArgumentSchema(
                    arguments=(
                        ToolArgument(
                            name="operation",
                            value_type=ToolValueType.STRING,
                            required=True,
                            description=(
                                "Thermodynamics operation: ideal_gas_pressure, "
                                "ideal_gas_volume, ideal_gas_temperature, "
                                "ideal_gas_moles, density_ideal_gas, "
                                "specific_gas_constant, heat_transfer, "
                                "sensible_heat, latent_heat, thermal_efficiency, "
                                "refrigeration_cop, heat_pump_cop, first_law, "
                                "or entropy."
                            ),
                        ),
                        ToolArgument(
                            name="pressure",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Absolute gas pressure.",
                        ),
                        ToolArgument(
                            name="volume",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Gas volume.",
                        ),
                        ToolArgument(
                            name="temperature",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Absolute temperature in kelvin.",
                        ),
                        ToolArgument(
                            name="moles",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Amount of substance in moles.",
                        ),
                        ToolArgument(
                            name="gas_constant",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description=(
                                "Specific or universal gas constant, "
                                "depending on the selected operation."
                            ),
                        ),
                        ToolArgument(
                            name="molar_mass",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Molar mass of the gas.",
                        ),
                        ToolArgument(
                            name="specific_heat",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Specific heat capacity.",
                        ),
                        ToolArgument(
                            name="mass",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Mass of the substance.",
                        ),
                        ToolArgument(
                            name="temperature_change",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Temperature change.",
                        ),
                        ToolArgument(
                            name="latent_heat",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Specific latent heat.",
                        ),
                        ToolArgument(
                            name="heat",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Heat transfer.",
                        ),
                        ToolArgument(
                            name="work",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Work transfer.",
                        ),
                        ToolArgument(
                            name="internal_energy_change",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Change in internal energy.",
                        ),
                        ToolArgument(
                            name="heat_in",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Heat input to a thermal engine.",
                        ),
                        ToolArgument(
                            name="heat_out",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Heat rejected by a thermal engine.",
                        ),
                        ToolArgument(
                            name="refrigeration_effect",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Heat removed from the refrigerated space.",
                        ),
                        ToolArgument(
                            name="work_input",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Work input to a refrigeration or heat-pump cycle.",
                        ),
                        ToolArgument(
                            name="entropy_change",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Entropy change.",
                        ),
                    )
                ),
                engineering_domain="mechanical",
                execution_type=ToolExecutionType.NATIVE,
                required_software=(),
                input_artifact_types=("thermodynamics_specification",),
                output_artifact_types=("calculation_result",),
                required_permissions=(
                    PermissionScope(
                        PermissionClass.READ,
                        "anne/runtime/thermodynamics",
                    ),
                ),
                retry_mode=RetryMode.NONE,
                max_timeout_ms=1000,
            ),
            thermodynamics_handler,
        )
    def _register_strength_of_materials_tool(self) -> None:
        """Register the safe deterministic engineering strength-of-materials tool."""
        self._tool_registry.register(
            ToolDescriptor(
                tool_id="anne.strength_of_materials",
                version="1.0.0",
                description=(
                    "Safe deterministic engineering strength-of-materials "
                    "calculations for stress, strain, elasticity, thermal "
                    "expansion, bending, and beam shear."
                ),
                capabilities=("engineering.strength_of_materials",),
                arguments=ToolArgumentSchema(
                    arguments=(
                        ToolArgument(
                            name="operation",
                            value_type=ToolValueType.STRING,
                            required=True,
                            description=(
                                "Strength-of-materials operation: "
                                "normal_stress, shear_stress, strain, "
                                "elongation, hookes_law, youngs_modulus, "
                                "factor_of_safety, thermal_strain, "
                                "thermal_expansion, bending_stress, or "
                                "beam_shear_stress."
                            ),
                        ),
                        ToolArgument(
                            name="force",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Applied force.",
                        ),
                        ToolArgument(
                            name="area",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Cross-sectional area.",
                        ),
                        ToolArgument(
                            name="elongation",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Change in length.",
                        ),
                        ToolArgument(
                            name="original_length",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Original specimen length.",
                        ),
                        ToolArgument(
                            name="length",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Member length.",
                        ),
                        ToolArgument(
                            name="youngs_modulus",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Young's modulus.",
                        ),
                        ToolArgument(
                            name="strain",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Engineering strain.",
                        ),
                        ToolArgument(
                            name="stress",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Stress.",
                        ),
                        ToolArgument(
                            name="failure_stress",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Failure stress.",
                        ),
                        ToolArgument(
                            name="working_stress",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Working stress.",
                        ),
                        ToolArgument(
                            name="coefficient_of_expansion",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Coefficient of thermal expansion.",
                        ),
                        ToolArgument(
                            name="temperature_change",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Temperature change.",
                        ),
                        ToolArgument(
                            name="moment",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Bending moment.",
                        ),
                        ToolArgument(
                            name="distance_from_neutral_axis",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Distance from the neutral axis.",
                        ),
                        ToolArgument(
                            name="area_moment_of_inertia",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Area moment of inertia.",
                        ),
                        ToolArgument(
                            name="shear_force",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Internal shear force.",
                        ),
                        ToolArgument(
                            name="first_moment_area",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="First moment of area Q.",
                        ),
                        ToolArgument(
                            name="thickness",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description="Section thickness at the point of interest.",
                        ),
                    )
                ),
                engineering_domain="mechanical",
                execution_type=ToolExecutionType.NATIVE,
                required_software=(),
                input_artifact_types=("strength_of_materials_specification",),
                output_artifact_types=("calculation_result",),
                required_permissions=(
                    PermissionScope(
                        PermissionClass.READ,
                        "anne/runtime/strength_of_materials",
                    ),
                ),
                retry_mode=RetryMode.NONE,
                max_timeout_ms=1000,
            ),
            strength_of_materials_handler,
        )

    def _register_statistics_tool(self) -> None:
        """Register the safe deterministic engineering statistics tool."""
        self._tool_registry.register(
            ToolDescriptor(
                tool_id="anne.statistics",
                version="1.0.0",
                description=(
                    "Safe deterministic statistics for engineering "
                    "calculations, including sums, means, medians, "
                    "modes, variance, standard deviation, extrema, "
                    "percentiles, and RMS."
                ),
                capabilities=("engineering.statistics",),
                arguments=ToolArgumentSchema(
                    arguments=(
                        ToolArgument(
                            name="operation",
                            value_type=ToolValueType.STRING,
                            required=True,
                            description="Statistics operation to perform.",
                        ),
                        ToolArgument(
                            name="values",
                            value_type=ToolValueType.ARRAY,
                            required=True,
                            description="Numeric dataset.",
                        ),
                        ToolArgument(
                            name="sample",
                            value_type=ToolValueType.BOOLEAN,
                            required=False,
                            description=(
                                "Whether to calculate a sample statistic "
                                "instead of a population statistic."
                            ),
                        ),
                        ToolArgument(
                            name="percentile",
                            value_type=ToolValueType.NUMBER,
                            required=False,
                            description=(
                                "Percentile from 0 through 100."
                            ),
                        ),
                    )
                ),
                required_permissions=(
                    PermissionScope(
                        PermissionClass.READ,
                        "anne/runtime/statistics",
                    ),
                ),
                retry_mode=RetryMode.NONE,
                max_timeout_ms=1000,
            ),
            statistics_handler,
        )
