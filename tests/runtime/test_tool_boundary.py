import unittest
from uuid import uuid4

from anne_runtime.contracts import (
    PermissionClass,
    PermissionDecision,
    PermissionScope,
    RetryMode,
    ToolCall,
)
from anne_runtime.errors import PermissionDeniedError
from anne_runtime.policy import PolicyBroker, PolicyRule
from anne_runtime.tooling import AuthorizedToolRunner, NoopToolExecutor


def make_call(permission_class=PermissionClass.READ):
    return ToolCall(
        schema_version="1.0",
        request_id=uuid4(),
        task_id=uuid4(),
        tool="demo.noop",
        operation="execute",
        arguments={},
        permissions=(
            PermissionScope(
                permission_class,
                "workspace/project",
            ),
        ),
        timeout_ms=1000,
        retry_mode=RetryMode.NONE,
        idempotency_key="idempotent-test",
    )


class ToolBoundaryTests(unittest.TestCase):
    def test_denied_call_never_reaches_executor(self):
        runner = AuthorizedToolRunner(
            PolicyBroker(),
            NoopToolExecutor(),
        )

        with self.assertRaises(PermissionDeniedError):
            runner.run(make_call())

    def test_allowed_call_reaches_only_noop_executor(self):
        broker = PolicyBroker([
            PolicyRule(
                PermissionClass.READ,
                "workspace/project",
                PermissionDecision.ALLOW,
            )
        ])

        result = AuthorizedToolRunner(
            broker,
            NoopToolExecutor(),
        ).run(make_call())

        self.assertEqual("SUCCEEDED", result.status.value)
        self.assertFalse(result.result["executed"])
