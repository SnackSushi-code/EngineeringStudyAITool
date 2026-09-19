from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from anne_runtime.adapter_execution import (
    AdapterExecutionBoundary,
    MockEngineeringAdapter,
    ResourceGrant,
)
from anne_runtime.adapters import AdapterRegistry
from anne_runtime.cancellation import CancellationRequested, CancellationToken
from anne_runtime.contracts import (
    PermissionClass,
    PermissionDecision,
    PermissionRequest,
    PermissionScope,
    RetryMode,
    ToolCall,
)
from anne_runtime.errors import RuntimeInvariantError
from anne_runtime.policy import PolicyBroker, PolicyRule


class AdapterExecutionTests(unittest.TestCase):
    def setUp(self):
        self.registry = AdapterRegistry()
        self.adapter = MockEngineeringAdapter()
        self.registry.register(self.adapter)

        self.policy = PolicyBroker(
            rules=[
                PolicyRule(
                    permission_class=PermissionClass.WRITE,
                    target_pattern="workspace",
                    decision=PermissionDecision.ALLOW,
                )
            ]
        )

        self.boundary = AdapterExecutionBoundary(
            self.registry,
            self.policy,
        )

    def make_call(self, tool: str = "anne.mock.engineering") -> ToolCall:
        return ToolCall(
            schema_version="0.2",
            request_id=uuid4(),
            task_id=uuid4(),
            tool=tool,
            operation="generate_artifact",
            arguments={},
            permissions=(
                PermissionScope(
                    permission_class=PermissionClass.WRITE,
                    scope="workspace",
                ),
            ),
            timeout_ms=5000,
            retry_mode=RetryMode.NONE,
            idempotency_key=f"adapter-test-{uuid4()}",
        )

    def make_authorization(self, call: ToolCall):
        requests = tuple(
            PermissionRequest(
                schema_version="0.2",
                request_id=call.request_id,
                task_id=call.task_id,
                principal_type="agent",
                principal_id="ann-e-runtime-test",
                permission_class=permission.permission_class,
                target=permission.scope,
                reason=f"Adapter execution: {call.tool}.{call.operation}",
            )
            for permission in call.permissions
        )

        return tuple(
            self.policy.authorize(request)
            for request in requests
        )

    def test_requires_authorization_snapshot(self):
        call = self.make_call()

        with self.assertRaises(RuntimeInvariantError):
            self.boundary.execute(
                call,
                authorization=(),
                grant=ResourceGrant(
                    workspace=Path(tempfile.mkdtemp()),
                ),
                cancellation=CancellationToken(),
            )

    def test_unknown_adapter_fails_closed(self):
        call = self.make_call("anne.unknown.adapter")
        authorization = self.make_authorization(call)

        with self.assertRaises(RuntimeInvariantError):
            self.boundary.execute(
                call,
                authorization=authorization,
                grant=ResourceGrant(
                    workspace=Path(tempfile.mkdtemp()),
                ),
                cancellation=CancellationToken(),
            )

    def test_successful_mock_execution(self):
        workspace = Path(tempfile.mkdtemp())
        call = self.make_call()
        authorization = self.make_authorization(call)

        result = self.boundary.execute(
            call,
            authorization=authorization,
            grant=ResourceGrant(
                workspace=workspace,
            ),
            cancellation=CancellationToken(),
        )

        self.assertEqual(result.request_id, call.request_id)
        self.assertEqual(result.task_id, call.task_id)

        self.assertEqual(
            result.result["adapter_id"],
            "anne.mock.engineering",
        )
        self.assertEqual(
            result.result["operation"],
            "generate_artifact",
        )
        self.assertEqual(
            result.status.value,
            "SUCCEEDED",
        )

        self.assertEqual(len(result.artifacts), 1)

        artifact = result.result["artifacts"][0]

        self.assertEqual(
            artifact["truth_state"],
            "GENERATED",
        )
        self.assertEqual(
            artifact["media_type"],
            "text/plain",
        )

        self.assertEqual(
            result.tool,
            "anne.mock.engineering",
        )
        self.assertEqual(
            result.adapter_version,
            "0.1.0",
        )
        self.assertEqual(
            result.validation_state,
            "GENERATED",
        )

    def test_cancellation_prevents_worker(self):
        call = self.make_call()
        authorization = self.make_authorization(call)

        cancellation = CancellationToken()
        cancellation.request("test cancellation")

        with self.assertRaises(CancellationRequested):
            self.boundary.execute(
                call,
                authorization=authorization,
                grant=ResourceGrant(
                    workspace=Path(tempfile.mkdtemp()),
                ),
                cancellation=cancellation,
            )


if __name__ == "__main__":
    unittest.main()
