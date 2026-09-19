from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from anne_runtime.contracts import PermissionClass, PermissionScope, RetryMode, ToolCall
from anne_runtime.execution_supervisor import ExecutionSupervisor, SupervisorInvariantError, SupervisorState
from anne_runtime.isolation import IsolationPolicy, PlatformCapabilities, WorkerDescriptor
from anne_runtime.worker_protocol import WorkerMessage, WorkerMessageType


def make_call() -> ToolCall:
    return ToolCall(
        schema_version="0.2",
        request_id=uuid4(),
        task_id=uuid4(),
        tool="anne.mock.engineering",
        operation="generate_artifact",
        arguments={},
        permissions=(PermissionScope(PermissionClass.WRITE, "workspace"),),
        timeout_ms=5000,
        retry_mode=RetryMode.NONE,
        idempotency_key=f"supervisor-test-{uuid4()}",
    )


def make_policy() -> IsolationPolicy:
    return IsolationPolicy(workspace=Path(tempfile.mkdtemp()), timeout_seconds=5)


def make_worker() -> WorkerDescriptor:
    return WorkerDescriptor("worker-test-001", "anne.mock.engineering", "0.1.0", "0.4")


class ExecutionSupervisorFoundationTests(unittest.TestCase):
    def test_authorization_is_required_before_execution(self):
        s, c = ExecutionSupervisor(), make_call()
        with self.assertRaises(SupervisorInvariantError):
            s.authorize(c, make_worker(), make_policy(), authorization=())

    def test_authorized_execution_starts_authorized(self):
        s, c = ExecutionSupervisor(), make_call()
        e = s.authorize(c, make_worker(), make_policy(), authorization=("ALLOW",))
        self.assertEqual(e.state, SupervisorState.AUTHORIZED)
        self.assertEqual(e.request_id, c.request_id)
        self.assertEqual(e.task_id, c.task_id)

    def test_terminal_state_cannot_reactivate(self):
        s, c = ExecutionSupervisor(), make_call()
        e = s.authorize(c, make_worker(), make_policy(), authorization=("ALLOW",))
        for state in (SupervisorState.STARTING, SupervisorState.READY, SupervisorState.RUNNING, SupervisorState.COMPLETED):
            e = s.transition(e.execution_id, state)
        e = s.cleanup(e.execution_id)
        self.assertEqual(e.state, SupervisorState.TERMINAL)
        with self.assertRaises(SupervisorInvariantError):
            s.transition(e.execution_id, SupervisorState.RUNNING)

    def test_cleanup_is_idempotent(self):
        s, c = ExecutionSupervisor(), make_call()
        e = s.authorize(c, make_worker(), make_policy(), authorization=("ALLOW",))
        e = s.transition(e.execution_id, SupervisorState.STARTING)
        e = s.cleanup(e.execution_id)
        again = s.cleanup(e.execution_id)
        self.assertEqual(again.state, SupervisorState.TERMINAL)
        self.assertTrue(again.cleanup_complete)

    def test_worker_identity_and_correlation_are_checked(self):
        s, c = ExecutionSupervisor(), make_call()
        e = s.authorize(c, make_worker(), make_policy(), authorization=("ALLOW",))
        e = s.transition(e.execution_id, SupervisorState.STARTING)
        good = WorkerMessage("0.1", c.request_id, c.task_id, "worker-test-001", WorkerMessageType.READY, 0, {})
        s.validate_worker_message(e.execution_id, good, expected_sequence=0)
        bad = WorkerMessage("0.1", uuid4(), c.task_id, "worker-test-001", WorkerMessageType.READY, 0, {})
        with self.assertRaises(SupervisorInvariantError):
            s.validate_worker_message(e.execution_id, bad, expected_sequence=0)

    def test_start_message_requires_starting_state(self):
        s, c = ExecutionSupervisor(), make_call()
        e = s.authorize(c, make_worker(), make_policy(), authorization=("ALLOW",))
        with self.assertRaises(SupervisorInvariantError):
            s.build_start_message(e.execution_id)
        e = s.transition(e.execution_id, SupervisorState.STARTING)
        msg = s.build_start_message(e.execution_id)
        self.assertEqual(msg.message_type, WorkerMessageType.START)
        self.assertEqual(msg.sequence, 0)

    def test_platform_capabilities_are_explicit(self):
        caps = PlatformCapabilities(process_isolation=True, forced_termination=True)
        s = ExecutionSupervisor(platform_capabilities=caps)
        self.assertTrue(s.platform_capabilities.process_isolation)
        self.assertTrue(s.platform_capabilities.forced_termination)
        self.assertFalse(s.platform_capabilities.network_isolation)


if __name__ == "__main__":
    unittest.main()
