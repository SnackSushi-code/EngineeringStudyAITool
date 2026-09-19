from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Lock


class CancellationRequested(Exception):
    """Raised by cooperative workers when cancellation has been requested."""


@dataclass(frozen=True)
class CancellationSnapshot:
    requested: bool
    reason: str | None


class CancellationToken:
    """Thread-safe cooperative cancellation token.

    Cancellation is advisory: an executor must periodically call ``throw_if_requested``.
    The runtime never assumes that a running worker can be safely killed from outside.
    """

    def __init__(self) -> None:
        self._event = Event()
        self._lock = Lock()
        self._reason: str | None = None

    def request(self, reason: str = "cancelled") -> bool:
        with self._lock:
            if self._event.is_set():
                return False
            self._reason = reason
            self._event.set()
            return True

    @property
    def is_requested(self) -> bool:
        return self._event.is_set()

    @property
    def reason(self) -> str | None:
        with self._lock:
            return self._reason

    def snapshot(self) -> CancellationSnapshot:
        with self._lock:
            return CancellationSnapshot(self._event.is_set(), self._reason)

    def throw_if_requested(self) -> None:
        if self._event.is_set():
            raise CancellationRequested(self.reason or "cancelled")

    def wait(self, timeout: float | None = None) -> bool:
        return self._event.wait(timeout)
