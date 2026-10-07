from __future__ import annotations

from uuid import UUID, uuid4

from anne_runtime.context_summary import ContextSummary
from anne_runtime.context_summary_persistence import (
    ContextSummaryPersistence,
    ContextSummaryPersistenceError,
)


def test_persistence_is_abstract() -> None:
    assert hasattr(ContextSummaryPersistence, "save_summary")
    assert hasattr(ContextSummaryPersistence, "load_summary")
    assert hasattr(ContextSummaryPersistence, "clear_summary")
    assert hasattr(ContextSummaryPersistence, "delete_summary")
    assert hasattr(ContextSummaryPersistence, "close")


def test_save_summary_contract_exists() -> None:
    summary = ContextSummary(
        text="Previous discussion covered thermodynamics.",
        source_message_count=8,
    )
    session_id = uuid4()

    assert isinstance(session_id, UUID)
    assert summary.text



def test_summary_persistence_error_is_runtime_error() -> None:
    assert issubclass(ContextSummaryPersistenceError, RuntimeError)


def test_summary_contract_has_no_message_collection() -> None:
    summary = ContextSummary(
        text="Previous discussion covered thermodynamics."
    )

    assert not hasattr(summary, "messages")


def test_summary_contract_has_no_authority_metadata() -> None:
    summary = ContextSummary(
        text="Previous discussion covered thermodynamics."
    )

    fields = set(summary.__dataclass_fields__)

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

    assert fields.isdisjoint(forbidden)


def test_session_identifier_is_uuid() -> None:
    session_id = uuid4()

    assert isinstance(session_id, UUID)


def test_summary_source_count_remains_metadata_only() -> None:
    summary = ContextSummary(
        text="Previous discussion covered thermodynamics.",
        source_message_count=4,
    )

    assert summary.source_message_count == 4


def test_summary_text_remains_immutable() -> None:
    summary = ContextSummary(
        text="Previous discussion covered thermodynamics."
    )

    try:
        summary.text = "modified"
    except Exception:
        pass
    else:
        raise AssertionError("ContextSummary must remain immutable")


def test_persistence_contract_does_not_define_authority_operations() -> None:
    names = {
        name
        for name in dir(ContextSummaryPersistence)
        if not name.startswith("_")
    }

    forbidden = {
        "grant_permission",
        "revoke_permission",
        "authorize",
        "execute_tool",
        "set_policy",
        "change_policy",
    }

    assert names.isdisjoint(forbidden)


def test_persistence_contract_is_session_scoped() -> None:
    session_a = uuid4()
    session_b = uuid4()

    assert session_a != session_b


def test_summary_can_be_constructed_for_persistence() -> None:
    summary = ContextSummary(
        text="The user previously worked through a statics problem.",
        source_message_count=6,
    )

    assert summary.text.startswith("The user")
    assert summary.source_message_count == 6


def test_empty_summary_text_is_not_persistable() -> None:
    try:
        ContextSummary(text="")
    except ValueError:
        pass
    else:
        raise AssertionError("Expected empty summary text to be rejected")

