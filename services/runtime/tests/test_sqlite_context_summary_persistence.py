from __future__ import annotations

import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from anne_runtime.context_summary import ContextSummary
from anne_runtime.context_summary_persistence import (
    ContextSummaryPersistence,
    ContextSummaryPersistenceError,
)
from anne_runtime.sqlite_context_summary_persistence import (
    SQLiteContextSummaryPersistence,
)


def make_summary(
    text: str = "Previous discussion covered thermodynamics.",
    source_message_count: int = 8,
) -> ContextSummary:
    return ContextSummary(
        text=text,
        source_message_count=source_message_count,
    )


def test_sqlite_implementation_satisfies_persistence_contract(
    tmp_path: Path,
) -> None:
    persistence = SQLiteContextSummaryPersistence(
        tmp_path / "summaries.sqlite3"
    )

    try:
        assert isinstance(persistence, ContextSummaryPersistence)
    finally:
        persistence.close()


def test_missing_summary_returns_none(tmp_path: Path) -> None:
    persistence = SQLiteContextSummaryPersistence(
        tmp_path / "summaries.sqlite3"
    )
    session_id = uuid4()

    try:
        assert persistence.load_summary(session_id) is None
    finally:
        persistence.close()


def test_save_and_load_summary(tmp_path: Path) -> None:
    database = tmp_path / "summaries.sqlite3"
    persistence = SQLiteContextSummaryPersistence(database)
    session_id = uuid4()
    summary = make_summary()

    try:
        persistence.save_summary(session_id, summary)

        loaded = persistence.load_summary(session_id)

        assert loaded == summary
        assert loaded is not summary
    finally:
        persistence.close()


def test_save_replaces_existing_summary(tmp_path: Path) -> None:
    persistence = SQLiteContextSummaryPersistence(
        tmp_path / "summaries.sqlite3"
    )
    session_id = uuid4()

    first = make_summary(
        text="First summary.",
        source_message_count=4,
    )
    second = make_summary(
        text="Updated summary.",
        source_message_count=12,
    )

    try:
        persistence.save_summary(session_id, first)
        persistence.save_summary(session_id, second)

        assert persistence.load_summary(session_id) == second
    finally:
        persistence.close()


def test_summaries_are_session_scoped(tmp_path: Path) -> None:
    persistence = SQLiteContextSummaryPersistence(
        tmp_path / "summaries.sqlite3"
    )
    session_a = uuid4()
    session_b = uuid4()

    summary_a = make_summary(
        text="Summary A.",
        source_message_count=3,
    )
    summary_b = make_summary(
        text="Summary B.",
        source_message_count=7,
    )

    try:
        persistence.save_summary(session_a, summary_a)
        persistence.save_summary(session_b, summary_b)

        assert persistence.load_summary(session_a) == summary_a
        assert persistence.load_summary(session_b) == summary_b
    finally:
        persistence.close()


def test_clear_summary_removes_summary(tmp_path: Path) -> None:
    persistence = SQLiteContextSummaryPersistence(
        tmp_path / "summaries.sqlite3"
    )
    session_id = uuid4()

    try:
        persistence.save_summary(session_id, make_summary())
        persistence.clear_summary(session_id)

        assert persistence.load_summary(session_id) is None
    finally:
        persistence.close()


def test_delete_summary_removes_summary(tmp_path: Path) -> None:
    persistence = SQLiteContextSummaryPersistence(
        tmp_path / "summaries.sqlite3"
    )
    session_id = uuid4()

    try:
        persistence.save_summary(session_id, make_summary())
        persistence.delete_summary(session_id)

        assert persistence.load_summary(session_id) is None
    finally:
        persistence.close()


def test_summary_survives_close_and_reopen(tmp_path: Path) -> None:
    database = tmp_path / "summaries.sqlite3"
    session_id = uuid4()
    summary = make_summary(
        text="Recovered summary.",
        source_message_count=16,
    )

    first = SQLiteContextSummaryPersistence(database)
    first.save_summary(session_id, summary)
    first.close()

    second = SQLiteContextSummaryPersistence(database)

    try:
        assert second.load_summary(session_id) == summary
    finally:
        second.close()


def test_database_parent_directory_is_created(tmp_path: Path) -> None:
    database = tmp_path / "nested" / "data" / "summaries.sqlite3"

    persistence = SQLiteContextSummaryPersistence(database)

    try:
        assert database.exists()
    finally:
        persistence.close()


def test_summary_table_contains_only_expected_columns(
    tmp_path: Path,
) -> None:
    database = tmp_path / "summaries.sqlite3"
    persistence = SQLiteContextSummaryPersistence(database)

    try:
        with sqlite3.connect(database) as connection:
            columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(context_summaries)"
                )
            }

        assert columns == {
            "session_id",
            "schema_version",
            "summary_text",
            "source_message_count",
        }
    finally:
        persistence.close()


def test_summary_table_has_unique_session_identifier(
    tmp_path: Path,
) -> None:
    database = tmp_path / "summaries.sqlite3"
    persistence = SQLiteContextSummaryPersistence(database)

    try:
        with sqlite3.connect(database) as connection:
            indexes = list(
                connection.execute(
                    "PRAGMA table_info(context_summaries)"
                )
            )

        session_column = next(
            row for row in indexes if row[1] == "session_id"
        )

        assert session_column[5] == 1
    finally:
        persistence.close()


def test_summary_persistence_has_no_authority_columns(
    tmp_path: Path,
) -> None:
    database = tmp_path / "summaries.sqlite3"
    persistence = SQLiteContextSummaryPersistence(database)

    try:
        with sqlite3.connect(database) as connection:
            columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(context_summaries)"
                )
            }

        forbidden = {
            "permissions",
            "authority",
            "policy",
            "tool",
            "tool_name",
            "execution",
            "timeout",
            "retry",
        }

        assert columns.isdisjoint(forbidden)
    finally:
        persistence.close()



def test_invalid_summary_type_is_rejected(tmp_path: Path) -> None:
    persistence = SQLiteContextSummaryPersistence(
        tmp_path / "summaries.sqlite3"
    )

    try:
        with pytest.raises(ContextSummaryPersistenceError):
            persistence.save_summary(
                uuid4(),
                "not a ContextSummary",  # type: ignore[arg-type]
            )
    finally:
        persistence.close()

