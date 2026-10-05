from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
from uuid import UUID


class ConversationSessionError(RuntimeError):
    """Raised when a conversation session cannot be safely modified."""


@dataclass
class ConversationSession:
    """Runtime-owned in-memory conversation session."""

    session_id: UUID
    messages: list[Mapping[str, Any]] = field(default_factory=list)

    def snapshot(self) -> tuple[Mapping[str, Any], ...]:
        """Return an immutable snapshot of the current conversation."""
        return tuple(dict(message) for message in self.messages)
