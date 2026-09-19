from __future__ import annotations

from .cancellation import CancellationToken
from .contracts import ToolCall, ToolResult
from .errors import RuntimeInvariantError
from .tooling import AuthorizedToolRunner


class ExecutionCoordinator:
    """Single controlled path from an authorized ToolCall to a ToolExecutor."""

    def __init__(self, runner: AuthorizedToolRunner):
        self._runner = runner

    def preflight(self, call: ToolCall, cancellation: CancellationToken):
        cancellation.throw_if_requested()
        return self._runner.authorize(call, cancellation)

    def execute(
        self,
        call: ToolCall,
        cancellation: CancellationToken,
        authorization=None,
    ) -> ToolResult:
        cancellation.throw_if_requested()
        result = self._runner.run(call, cancellation, authorization=authorization)
        cancellation.throw_if_requested()
        if result.request_id != call.request_id or result.task_id != call.task_id:
            raise RuntimeInvariantError("ToolResult correlation IDs do not match ToolCall")
        return result
