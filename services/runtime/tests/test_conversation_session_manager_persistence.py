from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from anne_runtime.conversation_session import ConversationSessionError
from anne_runtime.conversation_session_manager import ConversationSessionManager
from anne_runtime.conversation_session_persistence import (
    ConversationSessionPersistenceError,
)
from anne_runtime.sqlite_conversation_session_persistence import (
    SQLiteConversationSessionPersistence,
)


def make_persistence(tmp_path: Path):
    return SQLiteConversationSessionPersistence(
        tmp_path / "conversation_sessions.sqlite3"
    )


def test_create_and_append_persist(tmp_path: Path) -> None:
    persistence = make_persistence(tmp_path)
    manager = ConversationSessionManager(persistence=persistence)

    session_id = manager.create_session()

    manager.append_message(
        session_id,
        {"role": "user", "content": "Hello Ann-E"},
    )
    manager.append_message(
        session_id,
        {"role": "assistant", "content": "Hello."},
    )

    assert persistence.load_session(session_id) == (
        {"role": "user", "content": "Hello Ann-E"},
        {"role": "assistant", "content": "Hello."},
    )


def test_new_manager_hydrates_persisted_session(tmp_path: Path) -> None:
    persistence = make_persistence(tmp_path)

    manager_one = ConversationSessionManager(persistence=persistence)
    session_id = manager_one.create_session()

    manager_one.append_message(
        session_id,
        {"role": "user", "content": "Remember this."},
    )

    manager_two = ConversationSessionManager(persistence=persistence)

    assert manager_two.has_session(session_id) is True
    assert manager_two.get_conversation(session_id) == (
        {"role": "user", "content": "Remember this."},
    )
    assert manager_two.session_count == 1


def test_hydration_preserves_order_and_name(tmp_path: Path) -> None:
    persistence = make_persistence(tmp_path)

    manager_one = ConversationSessionManager(persistence=persistence)
    session_id = manager_one.create_session()

    manager_one.append_message(
        session_id,
        {
            "role": "user",
            "content": "First",
            "name": "Nick",
        },
    )
    manager_one.append_message(
        session_id,
        {"role": "assistant", "content": "Second"},
    )
    manager_one.append_message(
        session_id,
        {"role": "user", "content": "Third"},
    )

    manager_two = ConversationSessionManager(persistence=persistence)

    assert manager_two.get_conversation(session_id) == (
        {"role": "user", "content": "First", "name": "Nick"},
        {"role": "assistant", "content": "Second"},
        {"role": "user", "content": "Third"},
    )


def test_clear_persists_across_manager_instances(tmp_path: Path) -> None:
    persistence = make_persistence(tmp_path)

    manager_one = ConversationSessionManager(persistence=persistence)
    session_id = manager_one.create_session()

    manager_one.append_message(
        session_id,
        {"role": "user", "content": "Temporary"},
    )

    manager_one.clear_session(session_id)

    manager_two = ConversationSessionManager(persistence=persistence)

    assert manager_two.has_session(session_id) is True
    assert manager_two.get_conversation(session_id) == ()


def test_delete_persists_across_manager_instances(tmp_path: Path) -> None:
    persistence = make_persistence(tmp_path)

    manager_one = ConversationSessionManager(persistence=persistence)
    session_id = manager_one.create_session()

    manager_one.append_message(
        session_id,
        {"role": "user", "content": "Delete me"},
    )

    manager_one.delete_session(session_id)

    manager_two = ConversationSessionManager(persistence=persistence)

    assert manager_two.has_session(session_id) is False

    with pytest.raises(ConversationSessionError):
        manager_two.get_session(session_id)


def test_hydrated_session_respects_message_limit(tmp_path: Path) -> None:
    persistence = make_persistence(tmp_path)

    manager_one = ConversationSessionManager(persistence=persistence)
    session_id = manager_one.create_session()

    manager_one.append_message(
        session_id,
        {"role": "user", "content": "One"},
    )
    manager_one.append_message(
        session_id,
        {"role": "assistant", "content": "Two"},
    )

    manager_two = ConversationSessionManager(
        persistence=persistence,
        max_messages_per_session=2,
    )

    manager_two.get_session(session_id)

    with pytest.raises(
        ConversationSessionError,
        match="maximum number of 2 messages",
    ):
        manager_two.append_message(
            session_id,
            {"role": "user", "content": "Three"},
        )


def test_hydrated_session_respects_total_length_limit(tmp_path: Path) -> None:
    persistence = make_persistence(tmp_path)

    manager_one = ConversationSessionManager(persistence=persistence)
    session_id = manager_one.create_session()

    manager_one.append_message(
        session_id,
        {"role": "user", "content": "12345"},
    )

    manager_two = ConversationSessionManager(
        persistence=persistence,
        max_total_conversation_length=5,
    )

    manager_two.get_session(session_id)

    with pytest.raises(
        ConversationSessionError,
        match="maximum total content length of 5 characters",
    ):
        manager_two.append_message(
            session_id,
            {"role": "assistant", "content": "6"},
        )


def test_append_rolls_back_when_persistence_fails(tmp_path: Path) -> None:
    persistence = make_persistence(tmp_path)

    manager = ConversationSessionManager(persistence=persistence)
    session_id = manager.create_session()

    original_save = persistence.save_session

    def failing_save(session_id, messages):
        if messages:
            raise ConversationSessionPersistenceError(
                "forced append failure"
            )
        original_save(session_id, messages)

    persistence.save_session = failing_save

    with pytest.raises(
        ConversationSessionError,
        match="forced append failure",
    ):
        manager.append_message(
            session_id,
            {"role": "user", "content": "Should roll back"},
        )

    assert manager.get_conversation(session_id) == ()


def test_clear_failure_restores_messages(tmp_path: Path) -> None:
    persistence = make_persistence(tmp_path)

    manager = ConversationSessionManager(persistence=persistence)
    session_id = manager.create_session()

    manager.append_message(
        session_id,
        {"role": "user", "content": "Keep this"},
    )

    def failing_clear(session_id):
        raise ConversationSessionPersistenceError(
            "forced clear failure"
        )

    persistence.clear_session = failing_clear

    with pytest.raises(
        ConversationSessionError,
        match="forced clear failure",
    ):
        manager.clear_session(session_id)

    assert manager.get_conversation(session_id) == (
        {"role": "user", "content": "Keep this"},
    )


def test_unpersisted_session_still_raises(tmp_path: Path) -> None:
    persistence = make_persistence(tmp_path)
    manager = ConversationSessionManager(persistence=persistence)

    unknown_id = UUID("00000000-0000-0000-0000-000000000123")

    assert manager.has_session(unknown_id) is False

    with pytest.raises(
        ConversationSessionError,
        match="conversation session does not exist",
    ):
        manager.get_session(unknown_id)
