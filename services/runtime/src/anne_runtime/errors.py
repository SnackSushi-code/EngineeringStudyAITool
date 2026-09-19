from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RuntimeErrorInfo:
    code: str
    message: str
    retryable: bool
    request_id: str
    task_id: str
    details: dict[str, Any] = field(default_factory=dict)
    recovery: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "request_id": self.request_id,
            "task_id": self.task_id,
            "details": self.details,
            "recovery": self.recovery,
        }


class RuntimeInvariantError(Exception):
    """Raised when an internal runtime invariant is violated."""


class ContractValidationError(ValueError):
    """Raised when a runtime object fails its machine contract."""


class PermissionDeniedError(PermissionError):
    """Raised when policy does not authorize an operation."""


class InvalidTransitionError(RuntimeInvariantError):
    """Raised for an invalid task-state transition."""
