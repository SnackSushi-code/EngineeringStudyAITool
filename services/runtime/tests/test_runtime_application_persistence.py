from __future__ import annotations

from pathlib import Path

from anne_runtime.runtime_application import RuntimeApplication


def make_application(tmp_path: Path) -> RuntimeApplication:
    schema_dir = tmp_path / "packages" / "schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)

    return RuntimeApplication(
        repository_root=tmp_path,
    )


def test_runtime_application_creates_session_database(tmp_path: Path) -> None:
    application = make_application(tmp_path)

    database_path = (
        tmp_path
        / "runtime-data"
        / "conversation_sessions.sqlite3"
    )

    assert database_path.is_file()

    session_id = application.create_session()
    assert session_id


def test_runtime_application_session_survives_new_application(
    tmp_path: Path,
) -> None:
    application_one = make_application(tmp_path)

    session_id = application_one.create_session()

    application_one._conversation_sessions.append_message(
        __import__("uuid").UUID(session_id),
        {
            "role": "user",
            "content": "Persist this runtime session.",
        },
    )

    application_two = make_application(tmp_path)

    parsed_session_id = __import__("uuid").UUID(session_id)

    assert application_two._conversation_sessions.has_session(
        parsed_session_id
    )

    assert application_two._conversation_sessions.get_conversation(
        parsed_session_id
    ) == (
        {
            "role": "user",
            "content": "Persist this runtime session.",
        },
    )


def test_runtime_application_clear_persists_across_instances(
    tmp_path: Path,
) -> None:
    application_one = make_application(tmp_path)

    session_id = application_one.create_session()
    parsed_session_id = __import__("uuid").UUID(session_id)

    application_one._conversation_sessions.append_message(
        parsed_session_id,
        {
            "role": "user",
            "content": "This should be cleared.",
        },
    )

    application_one.clear_session(session_id)

    application_two = make_application(tmp_path)

    assert application_two._conversation_sessions.has_session(
        parsed_session_id
    )

    assert application_two._conversation_sessions.get_conversation(
        parsed_session_id
    ) == ()


def test_runtime_application_delete_persists_across_instances(
    tmp_path: Path,
) -> None:
    application_one = make_application(tmp_path)

    session_id = application_one.create_session()
    parsed_session_id = __import__("uuid").UUID(session_id)

    application_one._conversation_sessions.append_message(
        parsed_session_id,
        {
            "role": "user",
            "content": "This should be deleted.",
        },
    )

    application_one.delete_session(session_id)

    application_two = make_application(tmp_path)

    assert not application_two._conversation_sessions.has_session(
        parsed_session_id
    )
