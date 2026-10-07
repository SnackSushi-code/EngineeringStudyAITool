"""Contract tests for deterministic conversation context management."""

from __future__ import annotations

from anne_runtime.context_manager import (
    ContextManager,
    ContextManagerError,
    ContextRequest,
)


def message(
    role: str,
    content: str,
    name: str | None = None,
) -> dict[str, str]:
    result = {
        "role": role,
        "content": content,
    }

    if name is not None:
        result["name"] = name

    return result


def test_empty_conversation_returns_empty_context() -> None:
    manager = ContextManager()

    result = manager.build_context(
        ContextRequest(conversation=()),
    )

    assert result.messages == ()
    assert result.message_count == 0
    assert result.character_count == 0
    assert result.truncated is False
    assert result.dropped_message_count == 0


def test_conversation_is_preserved_when_under_budget() -> None:
    conversation = (
        message("user", "first"),
        message("assistant", "second"),
        message("user", "third"),
    )

    manager = ContextManager(
        max_messages=10,
        max_characters=100,
    )

    result = manager.build_context(
        ContextRequest(conversation=conversation),
    )

    assert result.messages == conversation
    assert result.message_count == 3
    assert result.character_count == len("first") + len("second") + len("third")
    assert result.truncated is False
    assert result.dropped_message_count == 0


def test_message_budget_keeps_newest_messages() -> None:
    conversation = (
        message("user", "one"),
        message("assistant", "two"),
        message("user", "three"),
        message("assistant", "four"),
    )

    manager = ContextManager(
        max_messages=2,
        max_characters=1000,
    )

    result = manager.build_context(
        ContextRequest(conversation=conversation),
    )

    assert result.messages == conversation[-2:]
    assert result.message_count == 2
    assert result.truncated is True
    assert result.dropped_message_count == 2


def test_character_budget_keeps_newest_messages_without_splitting() -> None:
    conversation = (
        message("user", "1111"),
        message("assistant", "2222"),
        message("user", "3333"),
    )

    manager = ContextManager(
        max_messages=10,
        max_characters=8,
    )

    result = manager.build_context(
        ContextRequest(conversation=conversation),
    )

    assert result.messages == conversation[-2:]
    assert result.character_count == 8
    assert result.truncated is True
    assert result.dropped_message_count == 1


def test_message_over_budget_is_skipped() -> None:
    manager = ContextManager(
        max_messages=10,
        max_characters=5,
    )

    conversation = (
        message("user", "this message is too large"),
    )

    result = manager.build_context(
        ContextRequest(conversation=conversation),
    )

    assert result.messages == ()
    assert result.message_count == 0
    assert result.character_count == 0
    assert result.truncated is True
    assert result.dropped_message_count == 1


def test_invalid_message_is_rejected() -> None:
    manager = ContextManager()

    conversation = (
        {
            "role": "user",
            "content": "",
        },
    )

    try:
        manager.build_context(
            ContextRequest(conversation=conversation),
        )
    except ContextManagerError:
        pass
    else:
        raise AssertionError("Expected ContextManagerError")


def test_message_order_is_restored_after_reverse_selection() -> None:
    conversation = (
        message("user", "one"),
        message("assistant", "two"),
        message("user", "three"),
        message("assistant", "four"),
    )

    manager = ContextManager(
        max_messages=3,
        max_characters=1000,
    )

    result = manager.build_context(
        ContextRequest(conversation=conversation),
    )

    assert result.messages == (
        conversation[1],
        conversation[2],
        conversation[3],
    )


def test_tool_messages_are_valid_context_messages() -> None:
    conversation = (
        message("user", "calculate this"),
        message(
            "assistant",
            '{"decision_type":"TOOL_PROPOSAL","tool":"calculator"}',
        ),
        message(
            "tool",
            '{"status":"completed","result":{"value":42}}',
            name="calculator",
        ),
        message("assistant", "The answer is 42."),
    )

    manager = ContextManager(
        max_messages=10,
        max_characters=1000,
    )

    result = manager.build_context(
        ContextRequest(conversation=conversation),
    )

    assert result.messages == conversation


def test_context_request_requires_tuple_conversation() -> None:
    try:
        ContextRequest(
            conversation=[
                message("user", "hello"),
            ],
        )
    except ContextManagerError:
        pass
    else:
        raise AssertionError("Expected ContextManagerError")


def test_context_manager_rejects_invalid_budgets() -> None:
    for kwargs in (
        {"max_messages": 0},
        {"max_characters": 0},
    ):
        try:
            ContextManager(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(
                f"Expected ValueError for {kwargs}"
            )


def test_context_result_is_immutable() -> None:
    manager = ContextManager()

    result = manager.build_context(
        ContextRequest(
            conversation=(
                message("user", "hello"),
            ),
        ),
    )

    try:
        result.messages = ()
    except Exception:
        pass
    else:
        raise AssertionError("Context result must be immutable")


def test_context_does_not_modify_source_conversation() -> None:
    conversation = (
        message("user", "one"),
        message("assistant", "two"),
        message("user", "three"),
    )

    original = tuple(dict(item) for item in conversation)

    manager = ContextManager(
        max_messages=2,
        max_characters=1000,
    )

    manager.build_context(
        ContextRequest(conversation=conversation),
    )

    assert conversation == original

def test_oversized_old_message_is_skipped_when_newer_message_fits() -> None:
    conversation = (
        message("user", "this message is intentionally too large"),
        message("assistant", "ok"),
    )

    manager = ContextManager(
        max_messages=10,
        max_characters=10,
    )

    result = manager.build_context(
        ContextRequest(conversation=conversation),
    )

    assert result.messages == (conversation[1],)
    assert result.message_count == 1
    assert result.character_count == 2
    assert result.truncated is True
    assert result.dropped_message_count == 1


def test_oversized_newest_message_is_skipped_without_failing() -> None:
    conversation = (
        message("user", "fits"),
        message("assistant", "this message is too large"),
    )

    manager = ContextManager(
        max_messages=10,
        max_characters=10,
    )

    result = manager.build_context(
        ContextRequest(conversation=conversation),
    )

    assert result.messages == (conversation[0],)
    assert result.message_count == 1
    assert result.character_count == 4
    assert result.truncated is True
    assert result.dropped_message_count == 1


def test_message_name_is_preserved() -> None:
    conversation = (
        message(
            "tool",
            '{"value":42}',
            name="calculator",
        ),
    )

    manager = ContextManager(
        max_messages=10,
        max_characters=100,
    )

    result = manager.build_context(
        ContextRequest(conversation=conversation),
    )

    assert result.messages == conversation
    assert result.messages[0]["name"] == "calculator"


def test_message_mapping_is_copied() -> None:
    source = {
        "role": "user",
        "content": "hello",
    }

    conversation = (source,)

    manager = ContextManager()

    result = manager.build_context(
        ContextRequest(conversation=conversation),
    )

    source["content"] = "modified"

    assert result.messages[0]["content"] == "hello"


def test_unknown_message_fields_are_not_forwarded() -> None:
    conversation = (
        {
            "role": "user",
            "content": "hello",
            "internal": "should not be forwarded",
        },
    )

    manager = ContextManager()

    result = manager.build_context(
        ContextRequest(conversation=conversation),
    )

    assert result.messages == (
        {
            "role": "user",
            "content": "hello",
        },
    )


def test_exact_character_budget_is_inclusive() -> None:
    conversation = (
        message("user", "12345"),
    )

    manager = ContextManager(
        max_messages=10,
        max_characters=5,
    )

    result = manager.build_context(
        ContextRequest(conversation=conversation),
    )

    assert result.messages == conversation
    assert result.character_count == 5
    assert result.truncated is False


def test_exact_message_budget_is_inclusive() -> None:
    conversation = (
        message("user", "one"),
        message("assistant", "two"),
    )

    manager = ContextManager(
        max_messages=2,
        max_characters=100,
    )

    result = manager.build_context(
        ContextRequest(conversation=conversation),
    )

    assert result.messages == conversation
    assert result.message_count == 2
    assert result.truncated is False


def test_tool_message_name_survives_truncation() -> None:
    conversation = (
        message("user", "old"),
        message("assistant", "proposal"),
        message(
            "tool",
            '{"status":"completed"}',
            name="calculator",
        ),
        message("assistant", "final"),
    )

    manager = ContextManager(
        max_messages=2,
        max_characters=100,
    )

    result = manager.build_context(
        ContextRequest(conversation=conversation),
    )

    assert result.messages == (
        conversation[2],
        conversation[3],
    )
    assert result.messages[0]["role"] == "tool"
    assert result.messages[0]["name"] == "calculator"

