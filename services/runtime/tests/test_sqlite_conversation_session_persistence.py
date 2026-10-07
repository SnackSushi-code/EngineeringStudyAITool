from __future__ import annotations

import sqlite3
import json
import os
import subprocess
import sys
from uuid import UUID, uuid4

import pytest

from anne_runtime.conversation_session_persistence import (
    ConversationSessionPersistenceError,
)
from anne_runtime.sqlite_conversation_session_persistence import (
    SQLiteConversationSessionPersistence,
)


def test_missing_session_returns_none(tmp_path):
    database = tmp_path / "sessions.db"

    with SQLiteConversationSessionPersistence(database) as persistence:
        assert persistence.load_session(uuid4()) is None


def test_save_and_load_round_trip(tmp_path):
    database = tmp_path / "sessions.db"
    session_id = uuid4()

    messages = (
        {
            "role": "user",
            "content": "Explain Kirchhoff's voltage law.",
        },
        {
            "role": "assistant",
            "content": "The algebraic sum of voltages around a closed loop is zero.",
        },
    )

    with SQLiteConversationSessionPersistence(database) as persistence:
        persistence.save_session(session_id, messages)

        loaded = persistence.load_session(session_id)

    assert loaded == messages


def test_message_order_is_preserved(tmp_path):
    database = tmp_path / "sessions.db"
    session_id = uuid4()

    messages = tuple(
        {
            "role": "user",
            "content": f"Message {index}",
        }
        for index in range(10)
    )

    with SQLiteConversationSessionPersistence(database) as persistence:
        persistence.save_session(session_id, messages)

        loaded = persistence.load_session(session_id)

    assert loaded == messages


def test_optional_name_is_preserved(tmp_path):
    database = tmp_path / "sessions.db"
    session_id = uuid4()

    messages = (
        {
            "role": "tool",
            "name": "anne.calculator",
            "content": "42",
        },
    )

    with SQLiteConversationSessionPersistence(database) as persistence:
        persistence.save_session(session_id, messages)

        loaded = persistence.load_session(session_id)

    assert loaded is not None
    assert loaded[0]["name"] == "anne.calculator"


def test_save_replaces_previous_conversation_atomically(tmp_path):
    database = tmp_path / "sessions.db"
    session_id = uuid4()

    first = (
        {
            "role": "user",
            "content": "First conversation.",
        },
    )

    second = (
        {
            "role": "user",
            "content": "Replacement conversation.",
        },
        {
            "role": "assistant",
            "content": "Replacement response.",
        },
    )

    with SQLiteConversationSessionPersistence(database) as persistence:
        persistence.save_session(session_id, first)
        persistence.save_session(session_id, second)

        loaded = persistence.load_session(session_id)

    assert loaded == second


def test_clear_removes_messages_but_retains_session(tmp_path):
    database = tmp_path / "sessions.db"
    session_id = uuid4()

    messages = (
        {
            "role": "user",
            "content": "Clear me.",
        },
    )

    with SQLiteConversationSessionPersistence(database) as persistence:
        persistence.save_session(session_id, messages)
        persistence.clear_session(session_id)

        loaded = persistence.load_session(session_id)

    assert loaded == ()


def test_delete_removes_session_and_messages(tmp_path):
    database = tmp_path / "sessions.db"
    session_id = uuid4()

    messages = (
        {
            "role": "user",
            "content": "Delete me.",
        },
    )

    with SQLiteConversationSessionPersistence(database) as persistence:
        persistence.save_session(session_id, messages)
        persistence.delete_session(session_id)

        loaded = persistence.load_session(session_id)

    assert loaded is None


def test_sessions_are_isolated(tmp_path):
    database = tmp_path / "sessions.db"
    first_session = uuid4()
    second_session = uuid4()

    first_messages = (
        {
            "role": "user",
            "content": "First session.",
        },
    )

    second_messages = (
        {
            "role": "user",
            "content": "Second session.",
        },
    )

    with SQLiteConversationSessionPersistence(database) as persistence:
        persistence.save_session(first_session, first_messages)
        persistence.save_session(second_session, second_messages)

        assert persistence.load_session(first_session) == first_messages
        assert persistence.load_session(second_session) == second_messages

        persistence.clear_session(first_session)

        assert persistence.load_session(first_session) == ()
        assert persistence.load_session(second_session) == second_messages


def test_database_and_parent_directory_are_created(tmp_path):
    database = tmp_path / "nested" / "runtime" / "sessions.db"

    assert not database.exists()

    with SQLiteConversationSessionPersistence(database):
        pass

    assert database.exists()


def test_database_schema_is_created(tmp_path):
    database = tmp_path / "sessions.db"

    with SQLiteConversationSessionPersistence(database):
        pass

    connection = sqlite3.connect(database)

    try:
        tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            )
        }
    finally:
        connection.close()

    assert "metadata" in tables
    assert "sessions" in tables
    assert "messages" in tables


def test_schema_version_is_stored(tmp_path):
    database = tmp_path / "sessions.db"

    with SQLiteConversationSessionPersistence(database):
        pass

    connection = sqlite3.connect(database)

    try:
        row = connection.execute(
            """
            SELECT value
            FROM metadata
            WHERE key = 'schema_version'
            """
        ).fetchone()
    finally:
        connection.close()

    assert row == ("1",)


def test_unsupported_schema_version_is_rejected(tmp_path):
    database = tmp_path / "sessions.db"
    session_id = uuid4()

    with SQLiteConversationSessionPersistence(database) as persistence:
        persistence.save_session(
            session_id,
            (
                {
                    "role": "user",
                    "content": "Version test.",
                },
            ),
        )

    connection = sqlite3.connect(database)

    try:
        connection.execute(
            """
            UPDATE sessions
            SET schema_version = 999
            WHERE session_id = ?
            """,
            (str(session_id),),
        )
        connection.commit()
    finally:
        connection.close()

    with SQLiteConversationSessionPersistence(database) as persistence:
        with pytest.raises(ConversationSessionPersistenceError):
            persistence.load_session(session_id)


def test_invalid_persisted_json_is_rejected(tmp_path):
    database = tmp_path / "sessions.db"
    session_id = uuid4()

    with SQLiteConversationSessionPersistence(database):
        pass

    connection = sqlite3.connect(database)

    try:
        connection.execute(
            """
            INSERT INTO sessions (
                session_id,
                schema_version
            )
            VALUES (?, 1)
            """,
            (str(session_id),),
        )

        connection.execute(
            """
            INSERT INTO messages (
                session_id,
                message_index,
                message_json
            )
            VALUES (?, 0, ?)
            """,
            (str(session_id), "{not valid json"),
        )

        connection.commit()
    finally:
        connection.close()

    with SQLiteConversationSessionPersistence(database) as persistence:
        with pytest.raises(ConversationSessionPersistenceError):
            persistence.load_session(session_id)


def test_non_mapping_message_is_rejected(tmp_path):
    database = tmp_path / "sessions.db"
    session_id = uuid4()

    with SQLiteConversationSessionPersistence(database) as persistence:
        with pytest.raises(ConversationSessionPersistenceError):
            persistence.save_session(
                session_id,
                ("not a mapping",),
            )


def test_empty_conversation_can_be_persisted(tmp_path):
    database = tmp_path / "sessions.db"
    session_id = uuid4()

    with SQLiteConversationSessionPersistence(database) as persistence:
        persistence.save_session(session_id, ())

        loaded = persistence.load_session(session_id)

    assert loaded == ()


def test_delete_isolated_from_other_sessions(tmp_path):
    database = tmp_path / "sessions.db"
    first_session = uuid4()
    second_session = uuid4()

    messages = (
        {
            "role": "user",
            "content": "Keep this.",
        },
    )

    with SQLiteConversationSessionPersistence(database) as persistence:
        persistence.save_session(first_session, messages)
        persistence.save_session(second_session, messages)

        persistence.delete_session(first_session)

        assert persistence.load_session(first_session) is None
        assert persistence.load_session(second_session) == messages


def test_persistence_survives_database_reopen(tmp_path):
    database = tmp_path / "sessions.db"
    session_id = UUID("12345678-1234-5678-1234-567812345678")

    messages = (
        {
            "role": "user",
            "content": "Persistence survives restart.",
        },
        {
            "role": "assistant",
            "content": "Confirmed.",
        },
    )

    with SQLiteConversationSessionPersistence(database) as persistence:
        persistence.save_session(session_id, messages)

    with SQLiteConversationSessionPersistence(database) as persistence:
        assert persistence.load_session(session_id) == messages
def test_cross_process_session_recovery(tmp_path):
    database = tmp_path / "sessions.db"
    session_id = uuid4()

    messages = (
        {
            "role": "user",
            "content": "Explain Kirchhoff's voltage law.",
        },
        {
            "role": "assistant",
            "content": "The algebraic sum of voltages around a closed loop is zero.",
        },
        {
            "role": "tool",
            "name": "anne.calculator",
            "content": "42",
        },
    )

    runtime_source = str(
        __import__("pathlib").Path(__file__).resolve().parents[1] / "src"
    )

    environment = os.environ.copy()
    existing_pythonpath = environment.get("PYTHONPATH")

    if existing_pythonpath:
        environment["PYTHONPATH"] = (
            runtime_source
            + os.pathsep
            + existing_pythonpath
        )
    else:
        environment["PYTHONPATH"] = runtime_source

    writer_code = """
import sys
from anne_runtime.sqlite_conversation_session_persistence import (
    SQLiteConversationSessionPersistence,
)
from uuid import UUID

database = sys.argv[1]
session_id = UUID(sys.argv[2])

messages = (
    {
        "role": "user",
        "content": "Explain Kirchhoff's voltage law.",
    },
    {
        "role": "assistant",
        "content": "The algebraic sum of voltages around a closed loop is zero.",
    },
    {
        "role": "tool",
        "name": "anne.calculator",
        "content": "42",
    },
)

with SQLiteConversationSessionPersistence(database) as persistence:
    persistence.save_session(session_id, messages)
"""

    reader_code = """
import json
import sys
from anne_runtime.sqlite_conversation_session_persistence import (
    SQLiteConversationSessionPersistence,
)
from uuid import UUID

database = sys.argv[1]
session_id = UUID(sys.argv[2])

with SQLiteConversationSessionPersistence(database) as persistence:
    messages = persistence.load_session(session_id)

print(json.dumps(list(messages), ensure_ascii=False))
"""

    writer = subprocess.run(
        [
            sys.executable,
            "-c",
            writer_code,
            str(database),
            str(session_id),
        ],
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )

    assert writer.returncode == 0, writer.stderr

    reader = subprocess.run(
        [
            sys.executable,
            "-c",
            reader_code,
            str(database),
            str(session_id),
        ],
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )

    assert reader.returncode == 0, reader.stderr

    recovered = tuple(json.loads(reader.stdout))

    assert recovered == messages

