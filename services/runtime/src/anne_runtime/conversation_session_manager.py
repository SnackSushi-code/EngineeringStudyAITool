from __future__ import annotations

from threading import RLock
from typing import Any, Mapping
from uuid import UUID, uuid4

from .conversation_session import (
    ConversationSession,
    ConversationSessionError,
)


MAX_SESSIONS = 128
MAX_MESSAGES_PER_SESSION = 64
MAX_MESSAGE_LENGTH = 16_000
MAX_TOTAL_CONVERSATION_LENGTH = 64_000


class ConversationSessionManager:
    """
    Runtime-owned in-memory conversation state.

    This component owns conversation history only. It has no access to
    model providers, tool permissions, policy, authority resolution,
    execution, or tool handlers.
    """

    def __init__(
        self,
        *,
        max_sessions: int = MAX_SESSIONS,
        max_messages_per_session: int = MAX_MESSAGES_PER_SESSION,
        max_message_length: int = MAX_MESSAGE_LENGTH,
        max_total_conversation_length: int = (
            MAX_TOTAL_CONVERSATION_LENGTH
        ),
    ) -> None:
        if max_sessions <= 0:
            raise ValueError("max_sessions must be greater than zero")

        if max_messages_per_session <= 0:
            raise ValueError(
                "max_messages_per_session must be greater than zero"
            )

        if max_message_length <= 0:
            raise ValueError(
                "max_message_length must be greater than zero"
            )

        if max_total_conversation_length <= 0:
            raise ValueError(
                "max_total_conversation_length must be greater than zero"
            )

        self._max_sessions = max_sessions
        self._max_messages_per_session = max_messages_per_session
        self._max_message_length = max_message_length
        self._max_total_conversation_length = (
            max_total_conversation_length
        )

        self._sessions: dict[UUID, ConversationSession] = {}
        self._lock = RLock()

    def create_session(self) -> UUID:
        """Create and return a new runtime-owned session identity."""
        with self._lock:
            if len(self._sessions) >= self._max_sessions:
                raise ConversationSessionError(
                    "maximum number of conversation sessions reached"
                )

            session_id = uuid4()

            while session_id in self._sessions:
                session_id = uuid4()

            self._sessions[session_id] = ConversationSession(
                session_id=session_id,
            )

            return session_id

    def get_session(self, session_id: UUID) -> ConversationSession:
        """Return a session or raise when the session does not exist."""
        with self._lock:
            try:
                return self._sessions[session_id]
            except KeyError as exc:
                raise ConversationSessionError(
                    f"conversation session does not exist: {session_id}"
                ) from exc

    def get_conversation(
        self,
        session_id: UUID,
    ) -> tuple[Mapping[str, Any], ...]:
        """Return a safe snapshot of session conversation history."""
        with self._lock:
            session = self.get_session(session_id)
            return session.snapshot()

    def append_message(
        self,
        session_id: UUID,
        message: Mapping[str, Any],
    ) -> None:
        """Append one validated conversation message."""
        if not isinstance(message, Mapping):
            raise ConversationSessionError(
                "conversation message must be a mapping"
            )

        role = message.get("role")
        content = message.get("content")

        if not isinstance(role, str) or not role.strip():
            raise ConversationSessionError(
                "conversation message role must be a non-empty string"
            )

        if not isinstance(content, str):
            raise ConversationSessionError(
                "conversation message content must be a string"
            )

        content = content.strip()

        if not content:
            raise ConversationSessionError(
                "conversation message content cannot be blank"
            )

        if len(content) > self._max_message_length:
            raise ConversationSessionError(
                "conversation message exceeds the maximum "
                f"length of {self._max_message_length} characters"
            )

        normalized: dict[str, Any] = {
            "role": role.strip(),
            "content": content,
        }

        name = message.get("name")

        if name is not None:
            if not isinstance(name, str) or not name.strip():
                raise ConversationSessionError(
                    "conversation message name must be a non-empty string"
                )

            normalized["name"] = name.strip()

        with self._lock:
            session = self.get_session(session_id)

            if (
                len(session.messages)
                >= self._max_messages_per_session
            ):
                raise ConversationSessionError(
                    "conversation session reached the maximum number "
                    f"of {self._max_messages_per_session} messages"
                )

            current_length = sum(
                len(str(item.get("content", "")))
                for item in session.messages
            )

            if (
                current_length + len(content)
                > self._max_total_conversation_length
            ):
                raise ConversationSessionError(
                    "conversation session exceeded the maximum total "
                    f"content length of "
                    f"{self._max_total_conversation_length} characters"
                )

            session.messages.append(normalized)

    def clear_session(self, session_id: UUID) -> None:
        """Remove all messages while retaining the session identity."""
        with self._lock:
            session = self.get_session(session_id)
            session.messages.clear()

    def delete_session(self, session_id: UUID) -> None:
        """Delete a runtime-owned session."""
        with self._lock:
            if session_id not in self._sessions:
                raise ConversationSessionError(
                    f"conversation session does not exist: {session_id}"
                )

            del self._sessions[session_id]

    def has_session(self, session_id: UUID) -> bool:
        """Return whether a session currently exists."""
        with self._lock:
            return session_id in self._sessions

    @property
    def session_count(self) -> int:
        """Return the number of active in-memory sessions."""
        with self._lock:
            return len(self._sessions)
