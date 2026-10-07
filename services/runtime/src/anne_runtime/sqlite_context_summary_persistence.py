from __future__ import annotations

import sqlite3
from pathlib import Path
from uuid import UUID

from .context_summary import ContextSummary
from .context_summary_persistence import (
    ContextSummaryPersistence,
    ContextSummaryPersistenceError,
)


class SQLiteContextSummaryPersistence(ContextSummaryPersistence):
    """SQLite-backed persistence for runtime-owned context summaries."""

    SCHEMA_VERSION = 1

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)

        parent = self._database_path.parent
        if parent != Path("."):
            parent.mkdir(parents=True, exist_ok=True)

        try:
            self._connection = sqlite3.connect(
                self._database_path,
                check_same_thread=False,
            )
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._initialize_schema()
        except sqlite3.Error as exc:
            raise ContextSummaryPersistenceError(
                f"failed to initialize summary database: {exc}"
            ) from exc

    def _initialize_schema(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS context_summaries (
                session_id TEXT PRIMARY KEY,
                schema_version INTEGER NOT NULL,
                summary_text TEXT NOT NULL,
                source_message_count INTEGER NOT NULL
            )
            """
        )
        self._connection.commit()

    @staticmethod
    def _session_key(session_id: UUID) -> str:
        if not isinstance(session_id, UUID):
            raise ContextSummaryPersistenceError(
                "session_id must be a UUID"
            )
        return str(session_id)

    def load_summary(self, session_id: UUID) -> ContextSummary | None:
        session_key = self._session_key(session_id)

        try:
            row = self._connection.execute(
                """
                SELECT schema_version, summary_text, source_message_count
                FROM context_summaries
                WHERE session_id = ?
                """,
                (session_key,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise ContextSummaryPersistenceError(
                f"failed to load summary: {exc}"
            ) from exc

        if row is None:
            return None

        schema_version, summary_text, source_message_count = row

        if schema_version != self.SCHEMA_VERSION:
            raise ContextSummaryPersistenceError(
                f"unsupported summary schema version: {schema_version}"
            )

        try:
            return ContextSummary(
                text=summary_text,
                source_message_count=source_message_count,
            )
        except ValueError as exc:
            raise ContextSummaryPersistenceError(
                f"persisted summary violates its contract: {exc}"
            ) from exc

    def save_summary(
        self,
        session_id: UUID,
        summary: ContextSummary,
    ) -> None:
        session_key = self._session_key(session_id)

        if not isinstance(summary, ContextSummary):
            raise ContextSummaryPersistenceError(
                "summary must be a ContextSummary"
            )

        try:
            self._connection.execute(
                """
                INSERT INTO context_summaries (
                    session_id,
                    schema_version,
                    summary_text,
                    source_message_count
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id)
                DO UPDATE SET
                    schema_version = excluded.schema_version,
                    summary_text = excluded.summary_text,
                    source_message_count = excluded.source_message_count
                """,
                (
                    session_key,
                    self.SCHEMA_VERSION,
                    summary.text,
                    summary.source_message_count,
                ),
            )
            self._connection.commit()
        except sqlite3.Error as exc:
            raise ContextSummaryPersistenceError(
                f"failed to save summary: {exc}"
            ) from exc

    def clear_summary(self, session_id: UUID) -> None:
        self._delete_summary(session_id)

    def delete_summary(self, session_id: UUID) -> None:
        self._delete_summary(session_id)

    def _delete_summary(self, session_id: UUID) -> None:
        session_key = self._session_key(session_id)

        try:
            self._connection.execute(
                """
                DELETE FROM context_summaries
                WHERE session_id = ?
                """,
                (session_key,),
            )
            self._connection.commit()
        except sqlite3.Error as exc:
            raise ContextSummaryPersistenceError(
                f"failed to delete summary: {exc}"
            ) from exc

    def close(self) -> None:
        try:
            self._connection.close()
        except sqlite3.Error as exc:
            raise ContextSummaryPersistenceError(
                f"failed to close summary database: {exc}"
            ) from exc

    def __enter__(self) -> "SQLiteContextSummaryPersistence":
        return self

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        self.close()
