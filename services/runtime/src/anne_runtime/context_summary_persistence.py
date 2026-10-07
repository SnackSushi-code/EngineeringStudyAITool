from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from .context_summary import ContextSummary


class ContextSummaryPersistenceError(RuntimeError):
    """Raised when persisted conversation context cannot be safely accessed."""


class ContextSummaryPersistence(ABC):
    """
    Persistence boundary for runtime-owned conversation context summaries.

    This interface deliberately has no access to model providers, tool
    handlers, permissions, policy, authority resolution, or execution.
    """

    @abstractmethod
    def load_summary(
        self,
        session_id: UUID,
    ) -> ContextSummary | None:
        """Load the persisted summary for one session, or return None."""

    @abstractmethod
    def save_summary(
        self,
        session_id: UUID,
        summary: ContextSummary,
    ) -> None:
        """Persist the complete context summary for one session."""

    @abstractmethod
    def clear_summary(self, session_id: UUID) -> None:
        """Remove the persisted summary while retaining the session."""

    @abstractmethod
    def delete_summary(self, session_id: UUID) -> None:
        """Delete all persisted summary state for one session."""

    @abstractmethod
    def close(self) -> None:
        """Release persistence resources."""
