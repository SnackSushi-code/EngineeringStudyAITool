from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from anne_runtime.context_manager import ContextManager
from anne_runtime.context_summary import ContextSummary
from anne_runtime.context_summary_persistence import (
    ContextSummaryPersistence,
)
from anne_runtime.intelligence_contracts import IntelligenceRequest


def make_message(
    role: str,
    content: str,
    name: str | None = None,
) -> dict[str, str]:
    message: dict[str, str] = {
        "role": role,
        "content": content,
    }

    if name is not None:
        message["name"] = name

    return message


class MemorySummaryPersistence(ContextSummaryPersistence):
    """Minimal test double for the summary persistence boundary."""

    def __init__(self) -> None:
        self._summaries: dict[str, ContextSummary] = {}

    def load_summary(self, session_id):
        return self._summaries.get(str(session_id))

    def save_summary(self, session_id, summary):
        self._summaries[str(session_id)] = summary

    def clear_summary(self, session_id):
        self._summaries.pop(str(session_id), None)

    def delete_summary(self, session_id):
        self._summaries.pop(str(session_id), None)

    def close(self):
        return None


def test_context_manager_can_assemble_recent_conversation() -> None:
    manager = ContextManager()

    snapshot = manager.build_context(
        (
            make_message("user", "What is the ideal gas law?"),
            make_message("assistant", "PV = nRT."),
        )
    )

    assert snapshot.messages == (
        make_message("user", "What is the ideal gas law?"),
        make_message("assistant", "PV = nRT."),
    )
    assert snapshot.truncated is False


def test_context_manager_preserves_tool_messages() -> None:
    manager = ContextManager()

    conversation = (
        make_message("assistant", "I will calculate the result."),
        make_message(
            "tool",
            '{"tool":"thermodynamics","result":"101.3 kPa"}',
            "thermodynamics",
        ),
        make_message("assistant", "The pressure is 101.3 kPa."),
    )

    snapshot = manager.build_context(conversation)

    assert snapshot.messages == conversation
    assert snapshot.message_count == 3


def test_context_manager_returns_summary_separately_from_messages() -> None:
    manager = ContextManager()

    conversation = (
        make_message("user", "We discussed fluid mechanics."),
        make_message("assistant", "We covered Bernoulli's equation."),
    )

    summary = ContextSummary(
        text="Earlier discussion covered fluid mechanics.",
        source_message_count=2,
    )

    snapshot = manager.build_context(
        conversation,
        summary=summary,
    )

    assert snapshot.messages == conversation
    assert snapshot.summary == summary


def test_context_manager_does_not_replace_current_user_intent() -> None:
    request = IntelligenceRequest(
        request_id=uuid4(),
        task_id=uuid4(),
        user_intent="Calculate the pressure.",
        conversation=(
            make_message("user", "Earlier we discussed density."),
            make_message("assistant", "Density is mass per volume."),
        ),
        metadata={},
    )

    assert request.user_intent == "Calculate the pressure."
    assert len(request.conversation) == 2


def test_context_summary_persistence_is_data_only() -> None:
    persistence = MemorySummaryPersistence()
    session_id = uuid4()

    summary = ContextSummary(
        text="Prior engineering discussion.",
        source_message_count=5,
    )

    persistence.save_summary(session_id, summary)

    assert persistence.load_summary(session_id) == summary


def test_context_summary_is_session_scoped() -> None:
    persistence = MemorySummaryPersistence()

    session_a = uuid4()
    session_b = uuid4()

    summary_a = ContextSummary(
        text="Session A summary.",
        source_message_count=3,
    )

    summary_b = ContextSummary(
        text="Session B summary.",
        source_message_count=7,
    )

    persistence.save_summary(session_a, summary_a)
    persistence.save_summary(session_b, summary_b)

    assert persistence.load_summary(session_a) == summary_a
    assert persistence.load_summary(session_b) == summary_b


def test_context_integration_does_not_expose_authority_fields() -> None:
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

    context_types = {
        ContextManager,
        ContextSummary,
        ContextSummaryPersistence,
    }

    for context_type in context_types:
        assert forbidden.isdisjoint(vars(context_type))


def test_context_manager_truncation_metadata_is_preserved() -> None:
    manager = ContextManager(
        max_context_messages=2,
        max_context_characters=10_000,
    )

    conversation = (
        make_message("user", "old"),
        make_message("assistant", "middle"),
        make_message("user", "new"),
    )

    snapshot = manager.build_context(conversation)

    assert snapshot.messages == conversation[-2:]
    assert snapshot.truncated is True
    assert snapshot.dropped_message_count == 1


def test_context_manager_character_budget_is_preserved() -> None:
    manager = ContextManager(
        max_context_messages=32,
        max_context_characters=10,
    )

    conversation = (
        make_message("user", "12345"),
        make_message("assistant", "67890"),
        make_message("user", "abcde"),
    )

    snapshot = manager.build_context(conversation)

    assert snapshot.character_count <= 10
    assert snapshot.truncated is True


def test_context_summary_source_count_is_not_authority_metadata() -> None:
    summary = ContextSummary(
        text="Earlier context.",
        source_message_count=12,
    )

    assert summary.source_message_count == 12
    assert not hasattr(summary, "permissions")
    assert not hasattr(summary, "authority")
    assert not hasattr(summary, "policy")
    assert not hasattr(summary, "tool")


def test_context_integration_supports_empty_prior_context() -> None:
    manager = ContextManager()

    snapshot = manager.build_context(())

    assert snapshot.messages == ()
    assert snapshot.message_count == 0
    assert snapshot.character_count == 0
    assert snapshot.truncated is False


def test_context_integration_preserves_message_order() -> None:
    manager = ContextManager()

    conversation = (
        make_message("user", "First"),
        make_message("assistant", "Second"),
        make_message("tool", "Third"),
        make_message("assistant", "Fourth"),
    )

    snapshot = manager.build_context(conversation)

    assert [message["content"] for message in snapshot.messages] == [
        "First",
        "Second",
        "Third",
        "Fourth",
    ]
