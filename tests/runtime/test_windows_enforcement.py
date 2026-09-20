from __future__ import annotations

import os
import unittest
from pathlib import Path
from uuid import uuid4
from anne_runtime.isolation import IsolationPolicy, WorkerDescriptor
from anne_runtime.platform_enforcement import (
    EnforcementControl,
    EnforcementRequest,
    PreparedEnforcement,
)
from anne_runtime.windows_enforcement import (
    WINDOWS_ADAPTER_VERSION,
    WindowsEnforcementAdapter,
    WindowsEnforcementError,
)


def make_request(
    *,
    workspace: Path | None = Path("workspace"),
    network_enabled: bool = False,
    memory_limit_bytes: int | None = None,
    cpu_limit_percent: int | None = None,
    process_limit: int | None = None,
    credential_ids: tuple[str, ...] = (),
    environment_allowlist: tuple[str, ...] = (),
) -> EnforcementRequest:
    return EnforcementRequest(
        execution_id=uuid4(),
        request_id=uuid4(),
        task_id=uuid4(),
        worker=WorkerDescriptor(
            worker_id="windows-test-worker",
            adapter_id="anne.windows.test",
            adapter_version="0.1.0",
            runtime_api="0.1",
        ),
        policy=IsolationPolicy(
            workspace=workspace,
            timeout_seconds=10.0,
            network_enabled=network_enabled,
            memory_limit_bytes=memory_limit_bytes,
            cpu_limit_percent=cpu_limit_percent,
            process_limit=process_limit,
            credential_ids=credential_ids,
            environment_allowlist=environment_allowlist,
        ),
    )


@unittest.skipUnless(os.name == "nt", "Windows-specific enforcement tests")
class WindowsEnforcementAdapterTests(unittest.TestCase):
    def test_adapter_reports_windows_platform(self) -> None:
        adapter = WindowsEnforcementAdapter()

        self.assertEqual(adapter.capabilities.platform, "windows")
        self.assertEqual(
            adapter.capabilities.adapter_version,
            WINDOWS_ADAPTER_VERSION,
        )

    def test_b1_does_not_claim_unimplemented_security_controls(self) -> None:
        adapter = WindowsEnforcementAdapter()

        self.assertEqual(adapter.capabilities.controls, frozenset())

    def test_workspace_is_reported_as_filesystem_gap(self) -> None:
        adapter = WindowsEnforcementAdapter()
        prepared = adapter.prepare(make_request())

        self.assertIsInstance(prepared, PreparedEnforcement)
        self.assertEqual(prepared.plan.platform, "windows")
        self.assertFalse(
            prepared.plan.is_enforced(EnforcementControl.FILESYSTEM_ISOLATION)
        )

        gap_controls = {gap.control for gap in prepared.plan.gaps}
        self.assertIn(EnforcementControl.FILESYSTEM_ISOLATION, gap_controls)

    def test_disabled_network_is_explicit_gap(self) -> None:
        adapter = WindowsEnforcementAdapter()
        prepared = adapter.prepare(
            make_request(network_enabled=False)
        )

        self.assertIn(
            EnforcementControl.NETWORK_ISOLATION,
            {gap.control for gap in prepared.plan.gaps},
        )
        self.assertFalse(
            prepared.plan.is_enforced(EnforcementControl.NETWORK_ISOLATION)
        )

    def test_requested_resource_controls_are_explicit_gaps(self) -> None:
        adapter = WindowsEnforcementAdapter()

        prepared = adapter.prepare(
            make_request(
                memory_limit_bytes=128 * 1024 * 1024,
                cpu_limit_percent=50,
                process_limit=8,
            )
        )

        gaps = {gap.control for gap in prepared.plan.gaps}

        self.assertIn(EnforcementControl.MEMORY_LIMITS, gaps)
        self.assertIn(EnforcementControl.CPU_LIMITS, gaps)
        self.assertIn(EnforcementControl.PROCESS_COUNT_LIMITS, gaps)

    def test_credentials_and_environment_are_explicit_gaps(self) -> None:
        adapter = WindowsEnforcementAdapter()

        prepared = adapter.prepare(
            make_request(
                credential_ids=("github-token",),
                environment_allowlist=("PATH",),
            )
        )

        gaps = {gap.control for gap in prepared.plan.gaps}

        self.assertIn(EnforcementControl.CREDENTIAL_ISOLATION, gaps)
        self.assertIn(EnforcementControl.ENVIRONMENT_ISOLATION, gaps)

    def test_preparation_does_not_claim_worker_started(self) -> None:
        adapter = WindowsEnforcementAdapter()
        prepared = adapter.prepare(make_request())

        self.assertTrue(prepared.handle_id.startswith("windows-prepared-"))
        self.assertEqual(prepared.plan.enforced_controls, frozenset())

    def test_release_is_idempotent_for_b1_preparation(self) -> None:
        adapter = WindowsEnforcementAdapter()
        prepared = adapter.prepare(make_request())

        adapter.release(prepared)
        adapter.release(prepared)

    def test_non_windows_construction_is_rejected(self) -> None:
        if os.name == "nt":
            self.skipTest("Non-Windows guard cannot be exercised on Windows")

        with self.assertRaises(WindowsEnforcementError):
            WindowsEnforcementAdapter()


if __name__ == "__main__":
    unittest.main()
