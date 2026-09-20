from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from threading import Event
from typing import Any, Mapping, Protocol

from .contracts import (
    PermissionScope,
    RetryMode,
    TaskState,
    ToolCall,
)
from .errors import ContractValidationError


TOOL_CONTRACT_VERSION = "1.0"


class ToolContractError(ContractValidationError):
    """Raised when a tool contract or invocation is invalid."""


class ToolExecutionError(RuntimeError):
    """Base error for tool-contract and execution failures."""


class ToolApprovalRequiredError(ToolExecutionError):
    """Raised when policy requires explicit approval before execution."""

    def __init__(
        self,
        decision: Any,
        permission_class: str,
        target: str,
    ) -> None:
        self.decision = decision
        self.permission_class = permission_class
        self.target = target
        super().__init__(
            f"Tool approval required: {permission_class} {target}"
        )
    """Raised when executable tool work fails."""


class ToolValidationState(StrEnum):
    NOT_VALIDATED = "NOT_VALIDATED"
    PASSED = "PASSED"
    FAILED = "FAILED"


class ToolValueType(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"
    ANY = "any"


@dataclass(frozen=True)
class ToolArgument:
    name: str
    value_type: ToolValueType
    required: bool = False
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ToolContractError("Tool argument name cannot be empty.")


@dataclass(frozen=True)
class ToolArgumentSchema:
    arguments: tuple[ToolArgument, ...] = ()

    def __post_init__(self) -> None:
        names = [item.name for item in self.arguments]
        if len(names) != len(set(names)):
            raise ToolContractError("Tool argument names must be unique.")

    def validate(self, supplied: Mapping[str, Any]) -> None:
        known = {item.name: item for item in self.arguments}
        unknown = set(supplied) - set(known)
        if unknown:
            raise ToolContractError(f"Unknown tool arguments: {sorted(unknown)}")

        missing = [
            item.name
            for item in self.arguments
            if item.required and item.name not in supplied
        ]
        if missing:
            raise ToolContractError(
                f"Missing required tool arguments: {sorted(missing)}"
            )

        for name, value in supplied.items():
            self._validate_value(name, value, known[name].value_type)

    @staticmethod
    def _validate_value(name: str, value: Any, value_type: ToolValueType) -> None:
        if value_type == ToolValueType.ANY:
            return
        checks = {
            ToolValueType.STRING: isinstance(value, str),
            ToolValueType.INTEGER: isinstance(value, int) and not isinstance(value, bool),
            ToolValueType.NUMBER: isinstance(value, (int, float)) and not isinstance(value, bool),
            ToolValueType.BOOLEAN: isinstance(value, bool),
            ToolValueType.OBJECT: isinstance(value, Mapping),
            ToolValueType.ARRAY: isinstance(value, (list, tuple)),
        }
        if not checks[value_type]:
            raise ToolContractError(
                f"Invalid type for argument '{name}': expected "
                f"{value_type.value}, got {type(value).__name__}"
            )


@dataclass(frozen=True)
class ToolDescriptor:
    tool_id: str
    version: str
    description: str
    capabilities: tuple[str, ...]
    arguments: ToolArgumentSchema
    required_permissions: tuple[PermissionScope, ...]
    retry_mode: RetryMode = RetryMode.NONE
    max_timeout_ms: int = 60_000

    def __post_init__(self) -> None:
        if not self.tool_id.strip():
            raise ToolContractError("Tool ID cannot be empty.")
        if not self.version.strip():
            raise ToolContractError("Tool version cannot be empty.")
        if self.max_timeout_ms <= 0:
            raise ToolContractError("Tool maximum timeout must be positive.")
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ToolContractError("Tool capabilities must be unique.")

        seen: set[tuple[object, str]] = set()
        for permission in self.required_permissions:
            key = (permission.permission_class, permission.scope)
            if key in seen:
                raise ToolContractError(f"Duplicate permission declaration: {key}")
            seen.add(key)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": TOOL_CONTRACT_VERSION,
            "tool_id": self.tool_id,
            "version": self.version,
            "description": self.description,
            "capabilities": list(self.capabilities),
            "arguments": [
                {
                    "name": item.name,
                    "type": item.value_type.value,
                    "required": item.required,
                    "description": item.description,
                }
                for item in self.arguments.arguments
            ],
            "required_permissions": [item.to_dict() for item in self.required_permissions],
            "retry_mode": self.retry_mode.value,
            "max_timeout_ms": self.max_timeout_ms,
        }


@dataclass
class ToolExecutionContext:
    request_id: Any
    task_id: Any
    tool_id: str
    tool_version: str
    attempt: int
    cancellation_event: Event = field(default_factory=Event)

    def is_cancelled(self) -> bool:
        return self.cancellation_event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled():
            raise ToolExecutionError("Tool execution cancelled.")


class ToolHandler(Protocol):
    def __call__(
        self,
        context: ToolExecutionContext,
        arguments: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        ...


class ResultValidator(Protocol):
    def validate(
        self,
        result: Mapping[str, Any],
    ) -> tuple[bool, tuple[Mapping[str, Any], ...]]:
        ...


@dataclass(frozen=True)
class ToolInvocation:
    call: ToolCall
    descriptor: ToolDescriptor

    def __post_init__(self) -> None:
        if self.call.tool != self.descriptor.tool_id:
            raise ToolContractError("Tool call and descriptor IDs do not match.")
        if self.call.timeout_ms <= 0:
            raise ToolContractError("Tool timeout must be positive.")
        if self.call.timeout_ms > self.descriptor.max_timeout_ms:
            raise ToolContractError("Requested timeout exceeds tool maximum.")
        if not self.call.idempotency_key.strip():
            raise ToolContractError("Tool call requires an idempotency key.")

        self.descriptor.arguments.validate(self.call.arguments)

        required = {
            (item.permission_class, item.scope)
            for item in self.descriptor.required_permissions
        }
        declared = {
            (item.permission_class, item.scope)
            for item in self.call.permissions
        }
        if required != declared:
            missing = sorted(
                (item[0].value, item[1])
                for item in required - declared
            )
            extra = sorted(
                (item[0].value, item[1])
                for item in declared - required
            )
            raise ToolContractError(
                f"Tool call permissions must exactly match descriptor. "
                f"missing={missing}, extra={extra}"
            )


@dataclass(frozen=True)
class ToolAuditEvent:
    request_id: Any
    task_id: Any
    tool_id: str
    tool_version: str
    operation: str
    status: str
    attempt: int
    authorization: tuple[Mapping[str, Any], ...]
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": str(self.request_id),
            "task_id": str(self.task_id),
            "tool": self.tool_id,
            "tool_version": self.tool_version,
            "operation": self.operation,
            "status": self.status,
            "attempt": self.attempt,
            "authorization": [dict(item) for item in self.authorization],
            "error_code": self.error_code,
        }
