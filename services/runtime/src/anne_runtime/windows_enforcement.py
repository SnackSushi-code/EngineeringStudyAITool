"""Windows-native enforcement implementation.

Phase 0.4.8-B2 introduces Windows Job Objects as the first real
OS-level enforcement mechanism.

The adapter reports a control as enforced only when the corresponding
Windows-native mechanism is configured successfully.
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass
from uuid import uuid4

from .platform_enforcement import (
    EnforcementCapabilities,
    EnforcementControl,
    EnforcementGap,
    EnforcementPlan,
    EnforcementRequest,
    PreparedEnforcement,
)


WINDOWS_ADAPTER_VERSION = "0.2.0"


class WindowsEnforcementError(RuntimeError):
    """Raised when Windows-native enforcement cannot be configured."""


# ---------------------------------------------------------------------------
# Windows constants
# ---------------------------------------------------------------------------

_KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)

JOB_OBJECT_LIMIT_WORKINGSET = 0x00000001
JOB_OBJECT_LIMIT_PROCESS_TIME = 0x00000002
JOB_OBJECT_LIMIT_JOB_TIME = 0x00000004
JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
JOB_OBJECT_LIMIT_AFFINITY = 0x00000010
JOB_OBJECT_LIMIT_PRIORITY_CLASS = 0x00000020
JOB_OBJECT_LIMIT_PRESERVE_JOB_TIME = 0x00000040
JOB_OBJECT_LIMIT_SCHEDULING_CLASS = 0x00000080
JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION = 0x00000400
JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x00000800
JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK = 0x00001000
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000

JOB_OBJECT_CPU_RATE_CONTROL_ENABLE = 0x1
JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP = 0x4

JobObjectExtendedLimitInformation = 9
JobObjectCpuRateControlInformation = 15


# ---------------------------------------------------------------------------
# Windows structures
# ---------------------------------------------------------------------------

class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", wintypes.ULARGE_INTEGER),
        ("WriteOperationCount", wintypes.ULARGE_INTEGER),
        ("OtherOperationCount", wintypes.ULARGE_INTEGER),
        ("ReadTransferCount", wintypes.ULARGE_INTEGER),
        ("WriteTransferCount", wintypes.ULARGE_INTEGER),
        ("OtherTransferCount", wintypes.ULARGE_INTEGER),
    ]


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
        ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _JOBOBJECT_CPU_RATE_CONTROL_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("ControlFlags", wintypes.DWORD),
        ("CpuRate", wintypes.DWORD),
    ]


# ---------------------------------------------------------------------------
# Win32 prototypes
# ---------------------------------------------------------------------------

_KERNEL32.CreateJobObjectW.argtypes = [
    wintypes.LPVOID,
    wintypes.LPCWSTR,
]
_KERNEL32.CreateJobObjectW.restype = wintypes.HANDLE

_KERNEL32.SetInformationJobObject.argtypes = [
    wintypes.HANDLE,
    wintypes.INT,
    wintypes.LPVOID,
    wintypes.DWORD,
]
_KERNEL32.SetInformationJobObject.restype = wintypes.BOOL

_KERNEL32.AssignProcessToJobObject.argtypes = [
    wintypes.HANDLE,
    wintypes.HANDLE,
]
_KERNEL32.AssignProcessToJobObject.restype = wintypes.BOOL

_KERNEL32.TerminateJobObject.argtypes = [
    wintypes.HANDLE,
    wintypes.UINT,
]
_KERNEL32.TerminateJobObject.restype = wintypes.BOOL

_KERNEL32.CloseHandle.argtypes = [
    wintypes.HANDLE,
]
_KERNEL32.CloseHandle.restype = wintypes.BOOL


def _raise_last_error(operation: str) -> None:
    error = ctypes.get_last_error()
    raise WindowsEnforcementError(
        f"{operation} failed with Win32 error {error}."
    )


@dataclass
class _JobHandle:
    """Owned native Job Object handle."""

    handle: int
    closed: bool = False

    def close(self) -> None:
        if self.closed:
            return

        if not _KERNEL32.CloseHandle(self.handle):
            _raise_last_error("CloseHandle")

        self.closed = True

    def terminate(self, exit_code: int = 1) -> None:
        if self.closed:
            return

        if not _KERNEL32.TerminateJobObject(self.handle, exit_code):
            _raise_last_error("TerminateJobObject")


class WindowsEnforcementAdapter:
    """Windows-native enforcement adapter.

    B2 provides real Job Object enforcement for:

    - forced termination;
    - descendant-process containment;
    - process-count limits;
    - per-process memory limits;
    - CPU hard-cap limits.

    Filesystem, network, credential, and environment isolation remain
    explicit gaps until their own native enforcement mechanisms exist.
    """

    _B2_VERSION = WINDOWS_ADAPTER_VERSION

    def __init__(self) -> None:
        if os.name != "nt":
            raise WindowsEnforcementError(
                "WindowsEnforcementAdapter requires Windows."
            )

        self._prepared: dict[str, _JobHandle] = {}

    @property
    def capabilities(self) -> EnforcementCapabilities:
        return EnforcementCapabilities(
            platform="windows",
            adapter_version=self._B2_VERSION,
            controls=frozenset(
                {
                    EnforcementControl.FORCED_TERMINATION,
                    EnforcementControl.DESCENDANT_CONTROL,
                    EnforcementControl.PROCESS_COUNT_LIMITS,
                    EnforcementControl.MEMORY_LIMITS,
                    EnforcementControl.CPU_LIMITS,
                }
            ),
        )

    def prepare(self, request: EnforcementRequest) -> PreparedEnforcement:
        policy = request.policy

        handle = _KERNEL32.CreateJobObjectW(None, None)
        if not handle:
            _raise_last_error("CreateJobObjectW")

        job = _JobHandle(handle=int(handle))

        try:
            extended = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()

            flags = (
                JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            )

            if policy.process_limit is not None:
                flags |= JOB_OBJECT_LIMIT_ACTIVE_PROCESS
                extended.BasicLimitInformation.ActiveProcessLimit = (
                    policy.process_limit
                )

            if policy.memory_limit_bytes is not None:
                flags |= JOB_OBJECT_LIMIT_PROCESS_MEMORY
                extended.ProcessMemoryLimit = policy.memory_limit_bytes

            extended.BasicLimitInformation.LimitFlags = flags

            if not _KERNEL32.SetInformationJobObject(
                job.handle,
                JobObjectExtendedLimitInformation,
                ctypes.byref(extended),
                ctypes.sizeof(extended),
            ):
                _raise_last_error("SetInformationJobObject(extended limits)")

            if policy.cpu_limit_percent is not None:
                cpu = _JOBOBJECT_CPU_RATE_CONTROL_INFORMATION()
                cpu.ControlFlags = (
                    JOB_OBJECT_CPU_RATE_CONTROL_ENABLE
                    | JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP
                )

                # Windows expresses CPU rate as 1/100 of a percent:
                # 100% => 10000.
                cpu.CpuRate = policy.cpu_limit_percent * 100

                if not _KERNEL32.SetInformationJobObject(
                    job.handle,
                    JobObjectCpuRateControlInformation,
                    ctypes.byref(cpu),
                    ctypes.sizeof(cpu),
                ):
                    _raise_last_error("SetInformationJobObject(CPU rate)")

            enforced = {
                EnforcementControl.FORCED_TERMINATION,
                EnforcementControl.DESCENDANT_CONTROL,
            }

            gaps: list[EnforcementGap] = []

            if policy.process_limit is not None:
                enforced.add(EnforcementControl.PROCESS_COUNT_LIMITS)
            else:
                gaps.append(
                    EnforcementGap(
                        EnforcementControl.PROCESS_COUNT_LIMITS,
                        "No process-count limit was requested by the policy.",
                    )
                )

            if policy.memory_limit_bytes is not None:
                enforced.add(EnforcementControl.MEMORY_LIMITS)
            else:
                gaps.append(
                    EnforcementGap(
                        EnforcementControl.MEMORY_LIMITS,
                        "No memory limit was requested by the policy.",
                    )
                )

            if policy.cpu_limit_percent is not None:
                enforced.add(EnforcementControl.CPU_LIMITS)
            else:
                gaps.append(
                    EnforcementGap(
                        EnforcementControl.CPU_LIMITS,
                        "No CPU limit was requested by the policy.",
                    )
                )

            # These mechanisms are not implemented in B2.
            gaps.extend(
                [
                    EnforcementGap(
                        EnforcementControl.FILESYSTEM_ISOLATION,
                        "Filesystem ACL/token isolation is deferred.",
                    ),
                    EnforcementGap(
                        EnforcementControl.NETWORK_ISOLATION,
                        "Network isolation is deferred.",
                    ),
                    EnforcementGap(
                        EnforcementControl.CREDENTIAL_ISOLATION,
                        "Credential brokering/isolation is deferred.",
                    ),
                ]
            )

            if policy.environment_allowlist:
                gaps.append(
                    EnforcementGap(
                        EnforcementControl.ENVIRONMENT_ISOLATION,
                        "Environment filtering is not yet attached to worker launch.",
                    )
                )

            plan = EnforcementPlan(
                platform="windows",
                adapter_version=self._B2_VERSION,
                enforced_controls=frozenset(enforced),
                gaps=tuple(gaps),
                workspace_root=policy.workspace,
                network_enabled=False,
                environment={},
            )

            handle_id = f"windows-job-{uuid4()}"
            self._prepared[handle_id] = job

            return PreparedEnforcement(
                handle_id=handle_id,
                plan=plan,
            )

        except Exception:
            job.close()
            raise

    def assign_process(
        self,
        prepared: PreparedEnforcement,
        process_handle: int,
    ) -> None:
        """Assign an already-created worker process to the prepared Job."""

        job = self._get_job(prepared)

        if not _KERNEL32.AssignProcessToJobObject(
            job.handle,
            wintypes.HANDLE(process_handle),
        ):
            _raise_last_error("AssignProcessToJobObject")

    def terminate(
        self,
        prepared: PreparedEnforcement,
        *,
        exit_code: int = 1,
    ) -> None:
        """Terminate the entire Job Object process tree."""

        job = self._get_job(prepared)
        job.terminate(exit_code)

    def release(self, prepared: PreparedEnforcement) -> None:
        """Release the Job Object.

        Because B2 enables KILL_ON_JOB_CLOSE, closing the Job Object also
        guarantees that assigned processes do not survive the supervisor's
        ownership boundary.
        """

        if not isinstance(prepared, PreparedEnforcement):
            raise TypeError("prepared must be PreparedEnforcement")

        job = self._prepared.pop(prepared.handle_id, None)
        if job is None:
            return

        job.close()

    def _get_job(self, prepared: PreparedEnforcement) -> _JobHandle:
        if not isinstance(prepared, PreparedEnforcement):
            raise TypeError("prepared must be PreparedEnforcement")

        try:
            return self._prepared[prepared.handle_id]
        except KeyError as exc:
            raise WindowsEnforcementError(
                f"Unknown or released enforcement handle: {prepared.handle_id}"
            ) from exc
