from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID

from .conversation_session_persistence import (
    ConversationSessionPersistence,
    ConversationSessionPersistenceError,
)


class SQLiteConversationSessionPersistence(
    ConversationSessionPersistence
):
    """SQLite-backed persistence for runtime-owned conversation sessions."""

    SCHEMA_VERSION = 1

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)

        if self._database_path.parent:
            self._database_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

        try:
            self._connection = sqlite3.connect(
                self._database_path,
                check_same_thread=False,
            )
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._initialize_schema()
        except (OSError, sqlite3.Error) as exc:
            raise ConversationSessionPersistenceError(
                f"failed to initialize session database: {exc}"
            ) from exc

    def _initialize_schema(self) -> None:
        try:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    schema_version INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    session_id TEXT NOT NULL,
                    message_index INTEGER NOT NULL,
                    message_json TEXT NOT NULL,
                    PRIMARY KEY (session_id, message_index),
                    FOREIGN KEY (session_id)
                        REFERENCES sessions(session_id)
                        ON DELETE CASCADE
                );

                INSERT INTO metadata (key, value)
                VALUES ('schema_version', '1')
                ON CONFLICT(key) DO NOTHING;
                """
            )
            self._connection.commit()
        except sqlite3.Error as exc:
            raise ConversationSessionPersistenceError(
                f"failed to initialize session schema: {exc}"
            ) from exc

    def load_session(
        self,
        session_id: UUID,
    ) -> tuple[Mapping[str, Any], ...] | None:
        try:
            row = self._connection.execute(
                """
                SELECT schema_version
                FROM sessions
                WHERE session_id = ?
                """,
                (str(session_id),),
            ).fetchone()

            if row is None:
                return None

            schema_version = int(row[0])

            if schema_version != self.SCHEMA_VERSION:
                raise ConversationSessionPersistenceError(
                    f"unsupported session schema version: "
                    f"{schema_version}"
                )

            rows = self._connection.execute(
                """
                SELECT message_json
                FROM messages
                WHERE session_id = ?
                ORDER BY message_index ASC
                """,
                (str(session_id),),
            ).fetchall()

            messages: list[Mapping[str, Any]] = []

            for (message_json,) in rows:
                try:
                    message = json.loads(message_json)
                except json.JSONDecodeError as exc:
                    raise ConversationSessionPersistenceError(
                        "persisted conversation contains invalid JSON"
                    ) from exc

                if not isinstance(message, dict):
                    raise ConversationSessionPersistenceError(
                        "persisted conversation message must be an object"
                    )

                messages.append(message)

            return tuple(messages)

        except ConversationSessionPersistenceError:
            raise
        except sqlite3.Error as exc:
            raise ConversationSessionPersistenceError(
                f"failed to load conversation session: {exc}"
            ) from exc

    def save_session(
        self,
        session_id: UUID,
        messages: tuple[Mapping[str, Any], ...],
    ) -> None:
        serialized_messages: list[str] = []

        try:
            for message in messages:
                if not isinstance(message, Mapping):
                    raise ConversationSessionPersistenceError(
                        "session message must be a mapping"
                    )

                serialized_messages.append(
                    json.dumps(
                        dict(message),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )

            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO sessions (
                        session_id,
                        schema_version
                    )
                    VALUES (?, ?)
                    ON CONFLICT(session_id)
                    DO UPDATE SET schema_version = excluded.schema_version
                    """,
                    (
                        str(session_id),
                        self.SCHEMA_VERSION,
                    ),
                )

                self._connection.execute(
                    """
                    DELETE FROM messages
                    WHERE session_id = ?
                    """,
                    (str(session_id),),
                )

                self._connection.executemany(
                    """
                    INSERT INTO messages (
                        session_id,
                        message_index,
                        message_json
                    )
                    VALUES (?, ?, ?)
                    """,
                    [
                        (str(session_id), index, message_json)
                        for index, message_json in enumerate(
                            serialized_messages
                        )
                    ],
                )

        except ConversationSessionPersistenceError:
            raise
        except (TypeError, ValueError) as exc:
            raise ConversationSessionPersistenceError(
                f"failed to serialize conversation session: {exc}"
            ) from exc
        except sqlite3.Error as exc:
            raise ConversationSessionPersistenceError(
                f"failed to save conversation session: {exc}"
            ) from exc

    def clear_session(self, session_id: UUID) -> None:
        try:
            with self._connection:
                self._connection.execute(
                    """
                    DELETE FROM messages
                    WHERE session_id = ?
                    """,
                    (str(session_id),),
                )

        except sqlite3.Error as exc:
            raise ConversationSessionPersistenceError(
                f"failed to clear conversation session: {exc}"
            ) from exc

    def delete_session(self, session_id: UUID) -> None:
        try:
            with self._connection:
                self._connection.execute(
                    """
                    DELETE FROM sessions
                    WHERE session_id = ?
                    """,
                    (str(session_id),),
                )

        except sqlite3.Error as exc:
            raise ConversationSessionPersistenceError(
                f"failed to delete conversation session: {exc}"
            ) from exc

    def close(self) -> None:
        try:
            self._connection.close()
        except sqlite3.Error as exc:
            raise ConversationSessionPersistenceError(
                f"failed to close session database: {exc}"
            ) from exc

    def __enter__(self) -> "SQLiteConversationSessionPersistence":
        return self

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        self.close()
