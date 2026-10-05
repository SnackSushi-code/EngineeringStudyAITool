from __future__ import annotations

from uuid import UUID

import pytest

from anne_runtime.conversation_session import ConversationSessionError
from anne_runtime.conversation_session_manager import (
    ConversationSessionManager,
)


def test_create_session_returns_unique_uuid():
    manager = ConversationSessionManager()

    first = manager.create_session()
    second = manager.create_session()

    assert isinstance(first, UUID)
    assert isinstance(second, UUID)
    assert first != second
    assert manager.session_count == 2


def test_append_and_read_conversation():
    manager = ConversationSessionManager()
    session_id = manager.create_session()

    manager.append_message(
        session_id,
        {
            "role": "user",
            "content": "Explain Kirchhoff's voltage law.",
        },
    )

    manager.append_message(
        session_id,
        {
            "role": "assistant",
            "content": "The algebraic sum of voltages around a closed loop is zero.",
        },
    )

    conversation = manager.get_conversation(session_id)

    assert len(conversation) == 2
    assert conversation[0]["role"] == "user"
    assert conversation[0]["content"] == (
        "Explain Kirchhoff's voltage law."
    )
    assert conversation[1]["role"] == "assistant"


def test_snapshot_does_not_expose_session_list():
    manager = ConversationSessionManager()
    session_id = manager.create_session()

    manager.append_message(
        session_id,
        {
            "role": "user",
            "content": "Original message.",
        },
    )

    snapshot = manager.get_conversation(session_id)

    assert isinstance(snapshot, tuple)

    with pytest.raises(AttributeError):
        snapshot.append({})


def test_clear_session_removes_messages_but_keeps_session():
    manager = ConversationSessionManager()
    session_id = manager.create_session()

    manager.append_message(
        session_id,
        {
            "role": "user",
            "content": "Test message.",
        },
    )

    manager.clear_session(session_id)

    assert manager.has_session(session_id)
    assert manager.get_conversation(session_id) == ()


def test_delete_session_removes_session():
    manager = ConversationSessionManager()
    session_id = manager.create_session()

    manager.delete_session(session_id)

    assert not manager.has_session(session_id)
    assert manager.session_count == 0

    with pytest.raises(ConversationSessionError):
        manager.get_conversation(session_id)


def test_unknown_session_is_rejected():
    manager = ConversationSessionManager()

    with pytest.raises(ConversationSessionError):
        manager.get_conversation(UUID(int=1))


def test_blank_role_is_rejected():
    manager = ConversationSessionManager()
    session_id = manager.create_session()

    with pytest.raises(ConversationSessionError):
        manager.append_message(
            session_id,
            {
                "role": "   ",
                "content": "Hello.",
            },
        )


def test_blank_content_is_rejected():
    manager = ConversationSessionManager()
    session_id = manager.create_session()

    with pytest.raises(ConversationSessionError):
        manager.append_message(
            session_id,
            {
                "role": "user",
                "content": "   ",
            },
        )


def test_message_length_limit_is_enforced():
    manager = ConversationSessionManager(
        max_message_length=10,
    )
    session_id = manager.create_session()

    with pytest.raises(ConversationSessionError):
        manager.append_message(
            session_id,
            {
                "role": "user",
                "content": "12345678901",
            },
        )


def test_message_count_limit_is_enforced():
    manager = ConversationSessionManager(
        max_messages_per_session=2,
    )
    session_id = manager.create_session()

    manager.append_message(
        session_id,
        {
            "role": "user",
            "content": "One",
        },
    )

    manager.append_message(
        session_id,
        {
            "role": "assistant",
            "content": "Two",
        },
    )

    with pytest.raises(ConversationSessionError):
        manager.append_message(
            session_id,
            {
                "role": "user",
                "content": "Three",
            },
        )


def test_total_conversation_length_limit_is_enforced():
    manager = ConversationSessionManager(
        max_total_conversation_length=10,
    )
    session_id = manager.create_session()

    manager.append_message(
        session_id,
        {
            "role": "user",
            "content": "12345",
        },
    )

    manager.append_message(
        session_id,
        {
            "role": "assistant",
            "content": "12345",
        },
    )

    with pytest.raises(ConversationSessionError):
        manager.append_message(
            session_id,
            {
                "role": "user",
                "content": "1",
            },
        )


def test_session_count_limit_is_enforced():
    manager = ConversationSessionManager(
        max_sessions=1,
    )

    manager.create_session()

    with pytest.raises(ConversationSessionError):
        manager.create_session()


def test_optional_name_is_preserved():
    manager = ConversationSessionManager()
    session_id = manager.create_session()

    manager.append_message(
        session_id,
        {
            "role": "tool",
            "name": "anne.calculator",
            "content": "42",
        },
    )

    conversation = manager.get_conversation(session_id)

    assert conversation[0]["name"] == "anne.calculator"


def test_invalid_name_is_rejected():
    manager = ConversationSessionManager()
    session_id = manager.create_session()

    with pytest.raises(ConversationSessionError):
        manager.append_message(
            session_id,
            {
                "role": "tool",
                "name": "   ",
                "content": "42",
            },
        )
