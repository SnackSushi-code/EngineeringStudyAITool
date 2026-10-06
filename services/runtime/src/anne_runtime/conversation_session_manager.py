"""Runtime-owned conversation session management."""

from __future__ import annotations

from threading import RLock
from typing import Any, Mapping
from uuid import UUID, uuid4

from .conversation_session import ConversationSession, ConversationSessionError
from .conversation_session_persistence import ConversationSessionPersistence


class ConversationSessionManager:
    """Manage runtime-owned conversation sessions."""

    MAX_SESSIONS = 128
    MAX_MESSAGES_PER_SESSION = 64
    MAX_MESSAGE_LENGTH = 16_000
    MAX_TOTAL_CONVERSATION_LENGTH = 64_000

    def __init__(
        self,
        *,
        max_sessions: int = MAX_SESSIONS,
        max_messages_per_session: int = MAX_MESSAGES_PER_SESSION,
        max_message_length: int = MAX_MESSAGE_LENGTH,
        max_total_conversation_length: int = MAX_TOTAL_CONVERSATION_LENGTH,
        persistence: ConversationSessionPersistence | None = None,
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

        self._sessions: dict[UUID, ConversationSession] = {}
        self._lock = RLock()

        self._max_sessions = max_sessions
        self._max_messages_per_session = max_messages_per_session
        self._max_message_length = max_message_length
        self._max_total_conversation_length = (
            max_total_conversation_length
        )
        self._persistence = persistence

    def create_session(self) -> UUID:
        """Create and return a new session identifier."""
        with self._lock:
            if len(self._sessions) >= self._max_sessions:
                raise ConversationSessionError(
                    "conversation session limit reached: "
                    f"{self._max_sessions} sessions"
                )

            session_id = uuid4()
            session = ConversationSession(session_id)

            if self._persistence is not None:
                try:
                    self._persistence.save_session(
                        session_id,
                        session.snapshot(),
                    )
                except Exception as exc:
                    raise ConversationSessionError(str(exc)) from exc

            self._sessions[session_id] = session
            return session_id

    def get_session(self, session_id: UUID) -> ConversationSession:
        """Return an active session or hydrate it from persistence."""
        with self._lock:
            session = self._sessions.get(session_id)

            if session is not None:
                return session

            if self._persistence is not None:
                try:
                    messages = self._persistence.load_session(session_id)
                except Exception as exc:
                    raise ConversationSessionError(str(exc)) from exc

                if messages is not None:
                    if len(self._sessions) >= self._max_sessions:
                        raise ConversationSessionError(
                            "conversation session limit reached: "
                            f"{self._max_sessions} sessions"
                        )

                    session = ConversationSession(session_id)

                    try:
                        for message in messages:
                            self._validate_and_append_loaded_message(
                                session,
                                message,
                            )
                    except ConversationSessionError:
                        raise
                    except Exception as exc:
                        raise ConversationSessionError(str(exc)) from exc

                    self._sessions[session_id] = session
                    return session

            raise ConversationSessionError(
                f"conversation session does not exist: {session_id}"
            )

    def get_conversation(
        self,
        session_id: UUID,
    ) -> tuple[Mapping[str, Any], ...]:
        """Return an immutable conversation snapshot."""
        with self._lock:
            session = self.get_session(session_id)
            return session.snapshot()

    def append_message(
        self,
        session_id: UUID,
        message: Mapping[str, Any],
    ) -> None:
        """Append a validated message to a session."""
        normalized = self._normalize_message(message)

        with self._lock:
            session = self.get_session(session_id)

            if len(session.messages) >= self._max_messages_per_session:
                raise ConversationSessionError(
                    "conversation session reached the maximum number "
                    f"of {self._max_messages_per_session} messages"
                )

            current_length = sum(
                len(str(item.get("content", "")))
                for item in session.messages
            )

            if (
                current_length + len(normalized["content"])
                > self._max_total_conversation_length
            ):
                raise ConversationSessionError(
                    "conversation session exceeded the maximum total "
                    "content length of "
                    f"{self._max_total_conversation_length} characters"
                )

            session.messages.append(normalized)

            if self._persistence is not None:
                try:
                    self._persistence.save_session(
                        session.session_id,
                        session.snapshot(),
                    )
                except Exception as exc:
                    session.messages.pop()
                    raise ConversationSessionError(str(exc)) from exc

    def clear_session(self, session_id: UUID) -> None:
        """Remove all messages while retaining the session identity."""
        with self._lock:
            session = self.get_session(session_id)
            previous_messages = list(session.messages)

            session.messages.clear()

            if self._persistence is not None:
                try:
                    self._persistence.clear_session(session_id)
                except Exception as exc:
                    session.messages[:] = previous_messages
                    raise ConversationSessionError(str(exc)) from exc

    def delete_session(self, session_id: UUID) -> None:
        """Delete a runtime-owned session."""
        with self._lock:
            session = self._sessions.get(session_id)

            if session is None:
                if self._persistence is not None:
                    try:
                        persisted = self._persistence.load_session(session_id)
                    except Exception as exc:
                        raise ConversationSessionError(str(exc)) from exc

                    if persisted is not None:
                        try:
                            self._persistence.delete_session(session_id)
                        except Exception as exc:
                            raise ConversationSessionError(str(exc)) from exc
                        return

                raise ConversationSessionError(
                    f"conversation session does not exist: {session_id}"
                )

            if self._persistence is not None:
                try:
                    self._persistence.delete_session(session_id)
                except Exception as exc:
                    raise ConversationSessionError(str(exc)) from exc

            del self._sessions[session_id]

    def has_session(self, session_id: UUID) -> bool:
        """Return whether a session currently exists."""
        with self._lock:
            if session_id in self._sessions:
                return True

            if self._persistence is not None:
                try:
                    return self._persistence.load_session(session_id) is not None
                except Exception:
                    return False

            return False

    @property
    def session_count(self) -> int:
        """Return the number of active in-memory sessions."""
        with self._lock:
            return len(self._sessions)

    def _normalize_message(
        self,
        message: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Validate and normalize a new conversation message."""
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

        return normalized

    def _validate_and_append_loaded_message(
        self,
        session: ConversationSession,
        message: Mapping[str, Any],
    ) -> None:
        """Validate persisted data using the same manager bounds."""
        normalized = self._normalize_message(message)

        if len(session.messages) >= self._max_messages_per_session:
            raise ConversationSessionError(
                "conversation session reached the maximum number "
                f"of {self._max_messages_per_session} messages"
            )

        current_length = sum(
            len(str(item.get("content", "")))
            for item in session.messages
        )

        if (
            current_length + len(normalized["content"])
            > self._max_total_conversation_length
        ):
            raise ConversationSessionError(
                "conversation session exceeded the maximum total "
                "content length of "
                f"{self._max_total_conversation_length} characters"
            )

        session.messages.append(normalized)
