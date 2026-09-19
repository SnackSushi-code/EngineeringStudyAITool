from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping
from uuid import UUID

from .errors import ContractValidationError


class TaskState(StrEnum):
    QUEUED = "QUEUED"
    PLANNING = "PLANNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    RUNNING = "RUNNING"
    VALIDATING = "VALIDATING"
    ROLLING_BACK = "ROLLING_BACK"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    DENIED = "DENIED"
    TIMED_OUT = "TIMED_OUT"


TERMINAL_STATES = frozenset({
    TaskState.SUCCEEDED,
    TaskState.FAILED,
    TaskState.CANCELLED,
    TaskState.DENIED,
    TaskState.TIMED_OUT,
})


class PermissionClass(StrEnum):
    READ = "READ"
    WRITE = "WRITE"
    EXECUTE = "EXECUTE"
    NETWORK = "NETWORK"
    DESTRUCTIVE = "DESTRUCTIVE"
    SECURITY_SENSITIVE = "SECURITY_SENSITIVE"
    SELF_UPDATE = "SELF_UPDATE"


class PermissionDecision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class RetryMode(StrEnum):
    NONE = "none"
    SAFE = "safe"


@dataclass(frozen=True)
class PermissionScope:
    permission_class: PermissionClass
    scope: str

    def __post_init__(self) -> None:
        if not self.scope:
            raise ValueError("Permission scope cannot be empty")

    def to_dict(self) -> dict[str, str]:
        return {"class": self.permission_class.value, "scope": self.scope}


@dataclass(frozen=True)
class TaskRequest:
    schema_version: str
    request_id: UUID
    task_id: UUID
    created_at: str
    source: str
    user_intent: str
    priority: str
    workspace_id: UUID
    requested_capabilities: tuple[str, ...]
    approval_required: bool
    approval_id: UUID | None
    input_artifacts: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "request_id": str(self.request_id),
            "task_id": str(self.task_id),
            "created_at": self.created_at,
            "source": self.source,
            "user_intent": self.user_intent,
            "priority": self.priority,
            "workspace_id": str(self.workspace_id),
            "requested_capabilities": list(self.requested_capabilities),
            "approval_context": {
                "required": self.approval_required,
                "approval_id": str(self.approval_id) if self.approval_id else None,
            },
            "input_artifacts": list(self.input_artifacts),
        }


@dataclass(frozen=True)
class ToolCall:
    schema_version: str
    request_id: UUID
    task_id: UUID
    tool: str
    operation: str
    arguments: Mapping[str, Any]
    permissions: tuple[PermissionScope, ...]
    timeout_ms: int
    retry_mode: RetryMode
    idempotency_key: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "request_id": str(self.request_id),
            "task_id": str(self.task_id),
            "tool": self.tool,
            "operation": self.operation,
            "arguments": dict(self.arguments),
            "permissions": [p.to_dict() for p in self.permissions],
            "timeout_ms": self.timeout_ms,
            "retry": {
                "mode": self.retry_mode.value,
                "idempotency_key": self.idempotency_key,
            },
        }


@dataclass(frozen=True)
class PermissionRequest:
    schema_version: str
    request_id: UUID
    principal_type: str
    principal_id: str
    permission_class: PermissionClass
    target: str
    reason: str
    task_id: UUID

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "request_id": str(self.request_id),
            "principal": {"type": self.principal_type, "id": self.principal_id},
            "action": {"class": self.permission_class.value, "target": self.target},
            "reason": self.reason,
            "task_id": str(self.task_id),
        }


@dataclass(frozen=True)
class PermissionDecisionRecord:
    decision: PermissionDecision
    approval_id: UUID | None
    policy_version: str
    expires_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "approval_id": str(self.approval_id) if self.approval_id else None,
            "policy_version": self.policy_version,
            "expires_at": self.expires_at,
        }


@dataclass(frozen=True)
class ToolResult:
    schema_version: str
    request_id: UUID
    task_id: UUID
    status: TaskState
    result: Mapping[str, Any]
    artifacts: tuple[str, ...]
    validation_state: str
    validation_checks: tuple[Mapping[str, Any], ...]
    tool: str
    tool_version: str
    adapter_version: str
    error: Mapping[str, Any] | None
    logs: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.status not in TERMINAL_STATES:
            raise ContractValidationError(
                f"ToolResult status must be terminal, got {self.status}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "request_id": str(self.request_id),
            "task_id": str(self.task_id),
            "status": self.status.value,
            "result": dict(self.result),
            "artifacts": list(self.artifacts),
            "validation": {
                "state": self.validation_state,
                "checks": [dict(c) for c in self.validation_checks],
            },
            "provenance": {
                "tool": self.tool,
                "tool_version": self.tool_version,
                "adapter_version": self.adapter_version,
            },
            "error": dict(self.error) if self.error else None,
            "logs": list(self.logs),
        }
