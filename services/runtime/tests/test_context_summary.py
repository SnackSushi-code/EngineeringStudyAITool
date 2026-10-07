from __future__ import annotations

from anne_runtime.context_summary import (
    ContextSummary,
    ContextSummaryError,
)


def test_summary_requires_non_empty_text() -> None:
    try:
        ContextSummary(text="")
    except ContextSummaryError:
        pass
    else:
        raise AssertionError("Expected ContextSummaryError")


def test_summary_accepts_normal_text() -> None:
    summary = ContextSummary(
        text="The user is working on an engineering calculation."
    )

    assert summary.text == (
        "The user is working on an engineering calculation."
    )


def test_summary_is_immutable() -> None:
    summary = ContextSummary(
        text="The user is working on an engineering calculation."
    )

    try:
        summary.text = "modified"
    except Exception:
        pass
    else:
        raise AssertionError("ContextSummary must be immutable")


def test_summary_preserves_source_message_count() -> None:
    summary = ContextSummary(
        text="Previous discussion covered thermodynamics.",
        source_message_count=12,
    )

    assert summary.source_message_count == 12


def test_summary_rejects_negative_source_message_count() -> None:
    try:
        ContextSummary(
            text="Previous discussion covered thermodynamics.",
            source_message_count=-1,
        )
    except ContextSummaryError:
        pass
    else:
        raise AssertionError("Expected ContextSummaryError")


def test_summary_rejects_non_integer_source_message_count() -> None:
    try:
        ContextSummary(
            text="Previous discussion covered thermodynamics.",
            source_message_count="12",
        )
    except ContextSummaryError:
        pass
    else:
        raise AssertionError("Expected ContextSummaryError")


def test_summary_has_no_authority_fields() -> None:
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


def test_summary_metadata_is_bounded() -> None:
    summary = ContextSummary(
        text="Previous discussion covered thermodynamics.",
        source_message_count=8,
    )

    assert summary.source_message_count == 8


def test_summary_text_must_be_string() -> None:
    try:
        ContextSummary(text=123)
    except ContextSummaryError:
        pass
    else:
        raise AssertionError("Expected ContextSummaryError")


def test_summary_does_not_contain_message_collection() -> None:
    summary = ContextSummary(
        text="Previous discussion covered thermodynamics."
    )

    assert not hasattr(summary, "messages")


def test_summary_contract_has_exact_expected_fields() -> None:
    fields = set(ContextSummary.__dataclass_fields__)

    assert fields == {
        "text",
        "source_message_count",
    }


def test_summary_error_is_value_error() -> None:
    assert issubclass(ContextSummaryError, ValueError)
