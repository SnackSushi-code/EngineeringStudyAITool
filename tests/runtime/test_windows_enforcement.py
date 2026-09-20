from __future__ import annotations

import os
import subprocess
import sys
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
            adapter_version=WINDOWS_ADAPTER_VERSION,
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
    def setUp(self) -> None:
        self.adapter = WindowsEnforcementAdapter()

    def test_adapter_reports_real_b2_capabilities(self) -> None:
        controls = self.adapter.capabilities.controls

        self.assertEqual(self.adapter.capabilities.platform, "windows")
        self.assertEqual(
            self.adapter.capabilities.adapter_version,
            WINDOWS_ADAPTER_VERSION,
        )
        self.assertIn(EnforcementControl.FORCED_TERMINATION, controls)
        self.assertIn(EnforcementControl.DESCENDANT_CONTROL, controls)
        self.assertIn(EnforcementControl.PROCESS_COUNT_LIMITS, controls)
        self.assertIn(EnforcementControl.MEMORY_LIMITS, controls)
        self.assertIn(EnforcementControl.CPU_LIMITS, controls)

        self.assertNotIn(EnforcementControl.FILESYSTEM_ISOLATION, controls)
        self.assertNotIn(EnforcementControl.NETWORK_ISOLATION, controls)
        self.assertNotIn(EnforcementControl.CREDENTIAL_ISOLATION, controls)

    def test_job_is_prepared_without_starting_worker(self) -> None:
        prepared = self.adapter.prepare(
            make_request(
                memory_limit_bytes=128 * 1024 * 1024,
                cpu_limit_percent=50,
                process_limit=8,
            )
        )

        try:
            self.assertTrue(prepared.handle_id.startswith("windows-job-"))
            self.assertTrue(
                prepared.plan.is_enforced(
                    EnforcementControl.FORCED_TERMINATION
                )
            )
            self.assertTrue(
                prepared.plan.is_enforced(
                    EnforcementControl.DESCENDANT_CONTROL
                )
            )
            self.assertTrue(
                prepared.plan.is_enforced(
                    EnforcementControl.PROCESS_COUNT_LIMITS
                )
            )
            self.assertTrue(
                prepared.plan.is_enforced(
                    EnforcementControl.MEMORY_LIMITS
                )
            )
            self.assertTrue(
                prepared.plan.is_enforced(
                    EnforcementControl.CPU_LIMITS
                )
            )
        finally:
            self.adapter.release(prepared)

    def test_requested_deferred_controls_remain_gaps(self) -> None:
        prepared = self.adapter.prepare(
            make_request(
                credential_ids=("github-token",),
                environment_allowlist=("PATH",),
            )
        )

        try:
            gaps = {gap.control for gap in prepared.plan.gaps}

            self.assertIn(
                EnforcementControl.FILESYSTEM_ISOLATION,
                gaps,
            )
            self.assertIn(
                EnforcementControl.NETWORK_ISOLATION,
                gaps,
            )
            self.assertIn(
                EnforcementControl.CREDENTIAL_ISOLATION,
                gaps,
            )
            self.assertIn(
                EnforcementControl.ENVIRONMENT_ISOLATION,
                gaps,
            )
        finally:
            self.adapter.release(prepared)

    def test_job_release_is_idempotent(self) -> None:
        prepared = self.adapter.prepare(make_request())

        self.adapter.release(prepared)
        self.adapter.release(prepared)

    def test_non_windows_construction_is_rejected(self) -> None:
        # This test runs only on non-Windows systems.
        if os.name == "nt":
            self.skipTest("Non-Windows guard cannot be exercised on Windows")

        with self.assertRaises(WindowsEnforcementError):
            WindowsEnforcementAdapter()


    def test_assign_and_terminate_real_process(self) -> None:
        """Verify that a real process can be assigned to and terminated by the Job."""
        import time

        prepared = self.adapter.prepare(
            make_request(process_limit=4)
        )

        process = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import time; time.sleep(300)",
            ]
        )

        try:
            process_handle = int(process._handle)

            self.adapter.assign_process(
                prepared,
                process_handle,
            )

            self.adapter.terminate(
                prepared,
                exit_code=17,
            )

            deadline = time.monotonic() + 5.0

            while (
                process.poll() is None
                and time.monotonic() < deadline
            ):
                time.sleep(0.05)

            self.assertIsNotNone(
                process.poll(),
                "Job Object termination did not terminate the assigned process",
            )
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

            self.adapter.release(prepared)
if __name__ == "__main__":
    unittest.main()
