from __future__ import annotations

from dataclasses import dataclass
from time import sleep
from typing import Callable, TypeVar

from .contracts import RetryMode

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    mode: RetryMode = RetryMode.NONE
    max_attempts: int = 1
    backoff_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds cannot be negative")
        if self.mode == RetryMode.NONE and self.max_attempts != 1:
            raise ValueError("NONE retry mode permits exactly one attempt")


def run_with_retry(
    operation: Callable[[], T],
    policy: RetryPolicy,
    *,
    is_retryable: Callable[[Exception], bool] | None = None,
) -> T:
    """Retry only according to an explicit safe retry policy.

    The caller is responsible for ensuring that SAFE operations are idempotent or
    protected by the ToolCall idempotency key.
    """
    predicate = is_retryable or (lambda exc: False)
    last_error: Exception | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            if attempt >= policy.max_attempts or not predicate(exc):
                raise
            if policy.backoff_seconds:
                sleep(policy.backoff_seconds * attempt)
    assert last_error is not None
    raise last_error
