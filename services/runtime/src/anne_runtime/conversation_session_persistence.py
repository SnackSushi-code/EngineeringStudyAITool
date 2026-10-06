from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping
from uuid import UUID


class ConversationSessionPersistenceError(RuntimeError):
    """Raised when persisted conversation state cannot be safely accessed."""


class ConversationSessionPersistence(ABC):
    """
    Persistence boundary for runtime-owned conversation sessions.

    This interface deliberately has no access to model providers, tool
    handlers, permissions, policy, authority resolution, or execution.
    """

    @abstractmethod
    def load_session(
        self,
        session_id: UUID,
    ) -> tuple[Mapping[str, Any], ...] | None:
        """Load a persisted session conversation, or return None."""

    @abstractmethod
    def save_session(
        self,
        session_id: UUID,
        messages: tuple[Mapping[str, Any], ...],
    ) -> None:
        """Persist the complete conversation for one session."""

    @abstractmethod
    def clear_session(self, session_id: UUID) -> None:
        """Remove all persisted messages while retaining the session."""

    @abstractmethod
    def delete_session(self, session_id: UUID) -> None:
        """Delete all persisted state for one session."""

    @abstractmethod
    def close(self) -> None:
        """Release persistence resources."""
