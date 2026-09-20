from __future__ import annotations

from threading import RLock

from .tool_contracts import ToolContractError, ToolDescriptor, ToolHandler


class ToolRegistry:
    """Explicit deterministic registry of executable tool implementations."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._tools: dict[str, tuple[ToolDescriptor, ToolHandler]] = {}

    def register(
        self,
        descriptor: ToolDescriptor,
        handler: ToolHandler,
        *,
        replace: bool = False,
    ) -> None:
        with self._lock:
            if descriptor.tool_id in self._tools and not replace:
                raise ToolContractError(
                    f"Tool already registered: {descriptor.tool_id}"
                )
            self._tools[descriptor.tool_id] = (descriptor, handler)

    def unregister(self, tool_id: str) -> None:
        with self._lock:
            if tool_id not in self._tools:
                raise KeyError(tool_id)
            del self._tools[tool_id]

    def get(self, tool_id: str) -> tuple[ToolDescriptor, ToolHandler]:
        with self._lock:
            if tool_id not in self._tools:
                raise KeyError(f"Unknown tool: {tool_id}")
            return self._tools[tool_id]

    def descriptor(self, tool_id: str) -> ToolDescriptor:
        return self.get(tool_id)[0]

    def list(self) -> tuple[ToolDescriptor, ...]:
        with self._lock:
            return tuple(item[0] for item in self._tools.values())

    def ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._tools)

    def __len__(self) -> int:
        with self._lock:
            return len(self._tools)
