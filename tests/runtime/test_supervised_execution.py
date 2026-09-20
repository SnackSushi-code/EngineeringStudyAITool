from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from uuid import uuid4

from anne_runtime.contracts import PermissionClass, PermissionScope, RetryMode, ToolCall
from anne_runtime.execution_supervisor import ExecutionSupervisor, SupervisorState
from anne_runtime.isolation import IsolationPolicy, WorkerDescriptor
from anne_runtime.observability import InMemoryEventSink, RuntimeTelemetry
from anne_runtime.supervised_execution import SupervisedExecution
from anne_runtime.worker_protocol import WorkerMessage


def make_call(timeout_ms: int = 1000) -> ToolCall:
    return ToolCall("0.2", uuid4(), uuid4(), "anne.test", "execute", {}, (PermissionScope(PermissionClass.WRITE, "workspace"),), timeout_ms, RetryMode.NONE, f"id-{uuid4()}")


def make_worker() -> WorkerDescriptor:
    return WorkerDescriptor("worker-integration-001", "anne.test", "1.0.0", "0.4")


def make_policy(timeout: float = 1.0) -> IsolationPolicy:
    return IsolationPolicy(Path(tempfile.mkdtemp()), timeout)


def echo_handler(message: WorkerMessage) -> dict[str, object]:
    return {"echo": message.payload, "worker": message.worker_id}


def slow_handler(message: WorkerMessage) -> dict[str, object]:
    time.sleep(2.0)
    return {"done": True}


class SupervisedExecutionTests(unittest.TestCase):
    def test_success_runs_under_supervisor_and_cleans_up(self) -> None:
        sink = InMemoryEventSink()
        runtime = SupervisedExecution(ExecutionSupervisor(), telemetry=RuntimeTelemetry(sink))
        call = make_call()
        result = runtime.execute(call, make_worker(), make_policy(), authorization=("ALLOW",), handler=echo_handler)
        self.assertEqual(result.state, SupervisorState.TERMINAL)
        self.assertEqual(result.response.message_type.value, "RESULT")
        self.assertEqual(result.response.payload["echo"], {})
        self.assertEqual(sink.events()[-1].name, "worker_cleanup_complete")

    def test_timeout_is_supervisor_owned_and_worker_is_terminated(self) -> None:
        runtime = SupervisedExecution(ExecutionSupervisor())
        call = make_call(timeout_ms=100)
        result = runtime.execute(call, make_worker(), make_policy(0.1), authorization=("ALLOW",), handler=slow_handler)
        self.assertEqual(result.state, SupervisorState.TERMINAL)
        self.assertEqual(result.error_code, "WORKER_TIMEOUT")

    def test_unknown_or_invalid_worker_path_does_not_leave_execution_active(self) -> None:
        runtime = SupervisedExecution(ExecutionSupervisor())
        call = make_call()
        result = runtime.execute(call, make_worker(), make_policy(), authorization=("ALLOW",), handler=lambda message: None)
        self.assertEqual(result.state, SupervisorState.TERMINAL)
        self.assertEqual(result.error_code, "WORKER_EXECUTION_FAILED")

    def test_authorization_failure_occurs_before_worker_creation(self) -> None:
        runtime = SupervisedExecution(ExecutionSupervisor())
        call = make_call()
        with self.assertRaises(Exception):
            runtime.execute(call, make_worker(), make_policy(), authorization=(), handler=echo_handler)


if __name__ == "__main__":
    unittest.main()
