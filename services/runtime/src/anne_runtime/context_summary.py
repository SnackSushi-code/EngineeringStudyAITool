"""Immutable conversation context summary contract."""

from __future__ import annotations

from dataclasses import dataclass


class ContextSummaryError(ValueError):
    """Raised when a conversation summary violates its contract."""


@dataclass(frozen=True)
class ContextSummary:
    """Bounded, immutable summary data for older conversation context."""

    text: str
    source_message_count: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise ContextSummaryError(
                "summary text must be a string"
            )

        if not self.text.strip():
            raise ContextSummaryError(
                "summary text must be non-empty"
            )

        if (
            not isinstance(self.source_message_count, int)
            or isinstance(self.source_message_count, bool)
        ):
            raise ContextSummaryError(
                "source_message_count must be an integer"
            )

        if self.source_message_count < 0:
            raise ContextSummaryError(
                "source_message_count must not be negative"
            )
