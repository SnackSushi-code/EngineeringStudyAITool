"""Deterministic conversation context selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .context_summary import ContextSummary


class ContextManagerError(ValueError):
    """Raised when conversation context cannot be safely constructed."""


@dataclass(frozen=True)
class ContextRequest:
    """Input contract for deterministic context construction."""

    conversation: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.conversation, tuple):
            raise ContextManagerError("conversation must be a tuple")

        for message in self.conversation:
            if not isinstance(message, Mapping):
                raise ContextManagerError(
                    "conversation entries must be mappings"
                )


@dataclass(frozen=True)
class ContextSnapshot:
    """Immutable bounded view of conversation context."""

    messages: tuple[Mapping[str, Any], ...]
    message_count: int
    character_count: int
    truncated: bool
    dropped_message_count: int
    summary: ContextSummary | None = None


class ContextManager:
    """Select newest conversation messages within deterministic budgets."""

    MAX_CONTEXT_MESSAGES = 32
    MAX_CONTEXT_CHARACTERS = 32_000

    def __init__(
        self,
        *,
        max_messages: int | None = None,
        max_characters: int | None = None,
        max_context_messages: int | None = None,
        max_context_characters: int | None = None,
    ) -> None:
        resolved_messages = self._resolve_budget(
            legacy_value=max_messages,
            context_value=max_context_messages,
            default=self.MAX_CONTEXT_MESSAGES,
            name="max_messages",
        )

        resolved_characters = self._resolve_budget(
            legacy_value=max_characters,
            context_value=max_context_characters,
            default=self.MAX_CONTEXT_CHARACTERS,
            name="max_characters",
        )

        self._max_messages = resolved_messages
        self._max_characters = resolved_characters

    @staticmethod
    def _resolve_budget(
        *,
        legacy_value: int | None,
        context_value: int | None,
        default: int,
        name: str,
    ) -> int:
        if legacy_value is not None and context_value is not None:
            if legacy_value != context_value:
                raise ValueError(
                    f"{name} and context budget aliases must match"
                )

        value = (
            context_value
            if context_value is not None
            else legacy_value
            if legacy_value is not None
            else default
        )

        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{name} must be an integer")

        if value <= 0:
            raise ValueError(f"{name} must be greater than zero")

        return value

    def build_context(
        self,
        request_or_conversation: ContextRequest
        | tuple[Mapping[str, Any], ...],
        *,
        summary: ContextSummary | None = None,
    ) -> ContextSnapshot:
        """
        Build a bounded context snapshot.

        The original Phase 5E ContextRequest API remains supported.
        Phase 5H additionally allows a conversation tuple directly and
        carries a data-only ContextSummary separately from messages.
        """
        if isinstance(request_or_conversation, ContextRequest):
            conversation = request_or_conversation.conversation
        elif isinstance(request_or_conversation, tuple):
            conversation = request_or_conversation
        else:
            raise ContextManagerError(
                "request must be a ContextRequest or conversation tuple"
            )

        if summary is not None and not isinstance(summary, ContextSummary):
            raise ContextManagerError(
                "summary must be a ContextSummary or None"
            )

        normalized = tuple(
            self._normalize_message(message)
            for message in conversation
        )

        if not normalized:
            return ContextSnapshot(
                messages=(),
                message_count=0,
                character_count=0,
                truncated=False,
                dropped_message_count=0,
                summary=summary,
            )

        selected_reversed: list[Mapping[str, Any]] = []
        character_count = 0

        for message in reversed(normalized):
            if len(selected_reversed) >= self._max_messages:
                break

            content = message["content"]

            # A message cannot be split. Skip messages that individually
            # exceed the context budget and continue looking for older
            # messages that can still fit.
            if len(content) > self._max_characters:
                continue

            # Preserve the Phase 5E deterministic behavior: if the message
            # would exceed the remaining character budget, skip it and
            # continue looking for older messages.
            if character_count + len(content) > self._max_characters:
                continue

            selected_reversed.append(message)
            character_count += len(content)

        selected = tuple(reversed(selected_reversed))
        dropped_message_count = len(normalized) - len(selected)

        return ContextSnapshot(
            messages=selected,
            message_count=len(selected),
            character_count=character_count,
            truncated=dropped_message_count > 0,
            dropped_message_count=dropped_message_count,
            summary=summary,
        )

    @staticmethod
    def _normalize_message(
        message: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        if not isinstance(message, Mapping):
            raise ContextManagerError(
                "conversation message must be a mapping"
            )

        role = message.get("role")
        content = message.get("content")

        if not isinstance(role, str) or not role.strip():
            raise ContextManagerError(
                "conversation message role must be a non-empty string"
            )

        if not isinstance(content, str):
            raise ContextManagerError(
                "conversation message content must be a string"
            )

        if not content:
            raise ContextManagerError(
                "conversation message content cannot be empty"
            )

        result: dict[str, Any] = {
            "role": role,
            "content": content,
        }

        if "name" in message:
            name = message["name"]

            if not isinstance(name, str) or not name.strip():
                raise ContextManagerError(
                    "conversation message name must be a non-empty string"
                )

            result["name"] = name

        return result
