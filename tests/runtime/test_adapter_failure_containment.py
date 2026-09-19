from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from anne_runtime.adapter_execution import (
    AdapterArtifact,
    AdapterExecutionBoundary,
    AdapterResult,
    ArtifactProvenance,
    MockEngineeringAdapter,
    ResourceGrant,
)
from anne_runtime.adapters import AdapterManifest, AdapterRegistry
from anne_runtime.cancellation import CancellationRequested, CancellationToken
from anne_runtime.contracts import (
    PermissionClass,
    PermissionDecision,
    PermissionRequest,
    PermissionScope,
    RetryMode,
    TaskState,
    ToolCall,
)
from anne_runtime.policy import PolicyBroker, PolicyRule


class RaisingAdapter:
    manifest = AdapterManifest(
        adapter_id="anne.test.raising",
        display_name="Raising Test Adapter",
        version="0.1.0",
        runtime_api="0.4",
        operations=("generate_artifact",),
        enabled=True,
    )

    def execute(self, call, grant, cancellation):
        raise RuntimeError("secret-token=do-not-leak")


class TimeoutAdapter:
    manifest = AdapterManifest(
        adapter_id="anne.test.timeout",
        display_name="Timeout Test Adapter",
        version="0.1.0",
        runtime_api="0.4",
        operations=("generate_artifact",),
        enabled=True,
    )

    def execute(self, call, grant, cancellation):
        raise TimeoutError("internal timeout detail")


class MalformedAdapter:
    manifest = AdapterManifest(
        adapter_id="anne.test.malformed",
        display_name="Malformed Test Adapter",
        version="0.1.0",
        runtime_api="0.4",
        operations=("generate_artifact",),
        enabled=True,
    )

    def execute(self, call, grant, cancellation):
        return {"not": "an AdapterResult"}


class EscapingArtifactAdapter:
    manifest = AdapterManifest(
        adapter_id="anne.test.escape",
        display_name="Escaping Artifact Test Adapter",
        version="0.1.0",
        runtime_api="0.4",
        operations=("generate_artifact",),
        enabled=True,
    )

    def execute(self, call, grant, cancellation):
        return AdapterResult(
            request_id=str(call.request_id),
            task_id=str(call.task_id),
            adapter_id=self.manifest.adapter_id,
            operation=call.operation,
            status=TaskState.SUCCEEDED,
            artifacts=(
                AdapterArtifact(
                    artifact_id="escape",
                    path=str(grant.workspace.parent / "outside.txt"),
                    media_type="text/plain",
                    provenance=ArtifactProvenance(
                        adapter_id=self.manifest.adapter_id,
                        adapter_version=self.manifest.version,
                        operation=call.operation,
                        truth_state="GENERATED",
                        generated_by_task=str(call.task_id),
                    ),
                ),
            ),
        )


class AdapterExecutionHardeningTests(unittest.TestCase):
    def setUp(self):
        self.registry = AdapterRegistry()
        self.policy = PolicyBroker(
            rules=[
                PolicyRule(
                    permission_class=PermissionClass.WRITE,
                    target_pattern="workspace",
                    decision=PermissionDecision.ALLOW,
                )
            ]
        )
        self.boundary = AdapterExecutionBoundary(self.registry, self.policy)

    def make_call(self, tool: str) -> ToolCall:
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
            idempotency_key=f"hardening-{uuid4()}",
        )

    def make_authorization(self, call: ToolCall):
        requests = tuple(
            PermissionRequest(
                schema_version="0.2",
                request_id=call.request_id,
                task_id=call.task_id,
                principal_type="agent",
                principal_id="ann-e-runtime-hardening-test",
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

    def execute(self, adapter, *, workspace=None, timeout_seconds=30):
        self.registry.register(adapter)
        call = self.make_call(adapter.manifest.adapter_id)
        return self.boundary.execute(
            call,
            authorization=self.make_authorization(call),
            grant=ResourceGrant(
                workspace=workspace or Path(tempfile.mkdtemp()),
                timeout_seconds=timeout_seconds,
            ),
            cancellation=CancellationToken(),
        )

    def test_adapter_exception_is_normalized_without_leaking_exception_text(self):
        result = self.execute(RaisingAdapter())

        self.assertEqual(TaskState.FAILED, result.status)
        self.assertEqual("ANN_E_ADAPTER_FAILURE", result.error["code"])
        self.assertEqual("Adapter execution failed.", result.error["message"])
        self.assertEqual("RuntimeError", result.error["details"]["exception_type"])

        model_visible_state = {
            "result": result.result,
            "error": result.error,
            "logs": result.logs,
        }

        self.assertNotIn("secret-token", str(model_visible_state))
        self.assertNotIn("do-not-leak", str(model_visible_state))

    def test_adapter_timeout_is_normalized(self):
        result = self.execute(TimeoutAdapter(), timeout_seconds=1)

        self.assertEqual(TaskState.TIMED_OUT, result.status)
        self.assertEqual("ANN_E_ADAPTER_TIMEOUT", result.error["code"])
        self.assertTrue(result.error["retryable"])

    def test_malformed_adapter_result_is_normalized(self):
        result = self.execute(MalformedAdapter())

        self.assertEqual(TaskState.FAILED, result.status)
        self.assertEqual(
            "ANN_E_ADAPTER_MALFORMED_RESULT",
            result.error["code"],
        )
        self.assertEqual(
            "Adapter returned an invalid result.",
            result.error["message"],
        )

    def test_artifact_path_escape_is_rejected_and_normalized(self):
        workspace = Path(tempfile.mkdtemp())

        result = self.execute(
            EscapingArtifactAdapter(),
            workspace=workspace,
        )

        self.assertEqual(TaskState.FAILED, result.status)
        self.assertEqual(
            "ANN_E_ADAPTER_MALFORMED_RESULT",
            result.error["code"],
        )

    def test_cancellation_requested_by_worker_propagates(self):
        class CancellingAdapter:
            manifest = AdapterManifest(
                adapter_id="anne.test.cancel",
                display_name="Cancellation Test Adapter",
                version="0.1.0",
                runtime_api="0.4",
                operations=("generate_artifact",),
                enabled=True,
            )

            def execute(self, call, grant, cancellation):
                cancellation.request("worker requested cancellation")
                cancellation.throw_if_requested()

        self.registry.register(CancellingAdapter())
        call = self.make_call("anne.test.cancel")

        with self.assertRaises(CancellationRequested):
            self.boundary.execute(
                call,
                authorization=self.make_authorization(call),
                grant=ResourceGrant(
                    workspace=Path(tempfile.mkdtemp())
                ),
                cancellation=CancellationToken(),
            )

    def test_resource_grant_requires_positive_timeout(self):
        with self.assertRaises(ValueError):
            ResourceGrant(
                workspace=Path(tempfile.mkdtemp()),
                timeout_seconds=0,
            )


if __name__ == "__main__":
    unittest.main()
