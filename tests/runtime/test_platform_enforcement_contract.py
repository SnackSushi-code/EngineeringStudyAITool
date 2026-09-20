from __future__ import annotations

import unittest
from pathlib import Path
from uuid import uuid4

from anne_runtime.isolation import IsolationPolicy, WorkerDescriptor
from anne_runtime.platform_enforcement import (
    EnforcementCapabilities,
    EnforcementControl,
    EnforcementContractError,
    EnforcementGap,
    EnforcementPlan,
    EnforcementRequest,
    PlatformEnforcementAdapter,
    PreparedEnforcement,
)


def make_request() -> EnforcementRequest:
    return EnforcementRequest(
        execution_id=uuid4(),
        request_id=uuid4(),
        task_id=uuid4(),
        worker=WorkerDescriptor(
            worker_id="worker-test-001",
            adapter_id="anne.mock.engineering",
            adapter_version="0.1.0",
            runtime_api="0.1",
        ),
        policy=IsolationPolicy(
            workspace=Path("workspace"),
            timeout_seconds=10,
            network_enabled=False,
        ),
    )


class PlatformEnforcementContractTests(unittest.TestCase):
    def test_capabilities_are_explicit(self) -> None:
        capabilities = EnforcementCapabilities(
            platform="test",
            adapter_version="0.1.0",
            controls=frozenset({
                EnforcementControl.PROCESS_ISOLATION,
                EnforcementControl.FORCED_TERMINATION,
            }),
        )
        self.assertTrue(capabilities.supports(EnforcementControl.PROCESS_ISOLATION))
        self.assertFalse(capabilities.supports(EnforcementControl.NETWORK_ISOLATION))

    def test_request_requires_non_nil_identity(self) -> None:
        request = make_request()
        self.assertEqual(request.worker.adapter_id, "anne.mock.engineering")
        with self.assertRaises(EnforcementContractError):
            EnforcementRequest(
                execution_id=request.execution_id,
                request_id=request.request_id,
                task_id=type(request.task_id)(int=0),
                worker=request.worker,
                policy=request.policy,
            )

    def test_unenforced_control_is_explicit_gap(self) -> None:
        plan = EnforcementPlan(
            platform="test",
            adapter_version="0.1.0",
            enforced_controls=frozenset({EnforcementControl.PROCESS_ISOLATION}),
            gaps=(
                EnforcementGap(
                    EnforcementControl.NETWORK_ISOLATION,
                    "platform adapter does not implement network isolation yet",
                ),
            ),
        )
        self.assertTrue(plan.is_enforced(EnforcementControl.PROCESS_ISOLATION))
        self.assertFalse(plan.is_enforced(EnforcementControl.NETWORK_ISOLATION))

    def test_network_enabled_requires_actual_network_enforcement(self) -> None:
        with self.assertRaises(EnforcementContractError):
            EnforcementPlan(
                platform="test",
                adapter_version="0.1.0",
                enforced_controls=frozenset(),
                network_enabled=True,
            )

    def test_enforced_control_cannot_also_be_a_gap(self) -> None:
        with self.assertRaises(EnforcementContractError):
            EnforcementPlan(
                platform="test",
                adapter_version="0.1.0",
                enforced_controls=frozenset({EnforcementControl.PROCESS_ISOLATION}),
                gaps=(
                    EnforcementGap(
                        EnforcementControl.PROCESS_ISOLATION,
                        "contradictory test case",
                    ),
                ),
            )

    def test_prepared_handle_does_not_claim_worker_started(self) -> None:
        plan = EnforcementPlan(
            platform="test",
            adapter_version="0.1.0",
            enforced_controls=frozenset(),
        )
        prepared = PreparedEnforcement("prep-001", plan)
        self.assertEqual(prepared.handle_id, "prep-001")

    def test_protocol_is_runtime_checkable_by_shape(self) -> None:
        class StubAdapter:
            @property
            def capabilities(self) -> EnforcementCapabilities:
                return EnforcementCapabilities(
                    platform="test",
                    adapter_version="0.1.0",
                    controls=frozenset(),
                )

            def prepare(self, request: EnforcementRequest) -> PreparedEnforcement:
                return PreparedEnforcement(
                    "prep-002",
                    EnforcementPlan(
                        platform="test",
                        adapter_version="0.1.0",
                        enforced_controls=frozenset(),
                    ),
                )

            def release(self, prepared: PreparedEnforcement) -> None:
                return None

        adapter: PlatformEnforcementAdapter = StubAdapter()
        prepared = adapter.prepare(make_request())
        adapter.release(prepared)
        self.assertEqual(prepared.handle_id, "prep-002")


if __name__ == "__main__":
    unittest.main()
