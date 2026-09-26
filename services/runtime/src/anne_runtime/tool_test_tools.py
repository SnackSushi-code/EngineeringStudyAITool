from __future__ import annotations

import time
from threading import Lock
from typing import Any, Mapping

from .contracts import PermissionClass, PermissionScope, RetryMode
from .tool_contracts import (
    ToolArgument,
    ToolArgumentSchema,
    ToolDescriptor,
    ToolExecutionContext,
    ToolValueType,
)


class CountingTool:
    def __init__(self) -> None:
        self.count = 0
        self._lock = Lock()

    def __call__(self, context: ToolExecutionContext, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        context.raise_if_cancelled()
        with self._lock:
            self.count += 1
        return {"echo": arguments["value"], "attempt": context.attempt}


class FailingOnceTool:
    def __init__(self) -> None:
        self.count = 0
        self._lock = Lock()

    def __call__(self, context: ToolExecutionContext, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        context.raise_if_cancelled()
        with self._lock:
            self.count += 1
            count = self.count
        if count == 1:
            raise RuntimeError("deterministic first-attempt failure")
        return {"value": arguments["value"], "attempt": context.attempt}


class SlowCooperativeTool:
    def __call__(self, context: ToolExecutionContext, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        deadline = time.monotonic() + float(arguments["seconds"])
        while time.monotonic() < deadline:
            context.raise_if_cancelled()
            time.sleep(0.005)
        return {"completed": True}


def _permission() -> PermissionScope:
    return PermissionScope(PermissionClass.READ, "test:value")


def counting_descriptor() -> ToolDescriptor:
    return ToolDescriptor(
        tool_id="test.counter",
        version="1.0.0",
        description="Deterministic counter tool.",
        capabilities=("test.echo",),
        arguments=ToolArgumentSchema((
            ToolArgument("value", ToolValueType.STRING, required=True),
        )),
        required_permissions=(_permission(),),
        retry_mode=RetryMode.NONE,
        max_timeout_ms=5_000,
    )


def retry_descriptor() -> ToolDescriptor:
    return ToolDescriptor(
        tool_id="test.retry",
        version="1.0.0",
        description="Deterministic safe-retry tool.",
        capabilities=("test.retry",),
        arguments=ToolArgumentSchema((
            ToolArgument("value", ToolValueType.STRING, required=True),
        )),
        required_permissions=(_permission(),),
        retry_mode=RetryMode.SAFE,
        max_timeout_ms=5_000,
    )


def slow_descriptor() -> ToolDescriptor:
    return ToolDescriptor(
        tool_id="test.slow",
        version="1.0.0",
        description="Deterministic cooperative timeout tool.",
        capabilities=("test.timeout",),
        arguments=ToolArgumentSchema((
            ToolArgument("seconds", ToolValueType.NUMBER, required=True),
        )),
        required_permissions=(_permission(),),
        retry_mode=RetryMode.NONE,
        max_timeout_ms=5_000,
    )
