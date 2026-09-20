"""Windows-native process enforcement using Windows Job Objects."""

from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass
from typing import Any

from .isolation import IsolationPolicy
from .platform_enforcement import (
    EnforcementCapabilities,
    EnforcementControl,
    EnforcementGap,
    EnforcementPlan,
    EnforcementRequest,
    PreparedEnforcement,
)


WINDOWS_ADAPTER_VERSION = "0.2.1"


class WindowsEnforcementError(RuntimeError):
    """Raised when Windows enforcement cannot be configured or used."""


def _raise_last_error(operation: str) -> None:
    error_code = ctypes.get_last_error()
    raise WindowsEnforcementError(
        f"{operation} failed with Windows error {error_code}"
    )


def _load_kernel32() -> Any:
    """Load kernel32 and configure the Win32 APIs used by this adapter."""

    if os.name != "nt":
        raise WindowsEnforcementError(
            "Windows enforcement is only available on Windows."
        )

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    kernel32.CreateJobObjectW.restype = ctypes.c_void_p

    kernel32.SetInformationJobObject.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
    ]
    kernel32.SetInformationJobObject.restype = ctypes.c_int

    kernel32.AssignProcessToJobObject.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    kernel32.AssignProcessToJobObject.restype = ctypes.c_int

    kernel32.TerminateJobObject.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
    ]
    kernel32.TerminateJobObject.restype = ctypes.c_int

    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int

    return kernel32


_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_JOB_OBJECT_CPU_RATE_CONTROL_INFORMATION = 15

JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000

JOB_OBJECT_CPU_RATE_CONTROL_ENABLE = 0x1
JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP = 0x4


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
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
        ("ControlFlags", ctypes.c_uint32),
        ("CpuRate", ctypes.c_uint32),
    ]


@dataclass
class _JobHandle:
    """Owned native Windows Job Object handle."""

    handle: int
    kernel32: Any

    def close(self) -> None:
        if self.handle:
            result = self.kernel32.CloseHandle(self.handle)
            self.handle = 0
            if not result:
                _raise_last_error("CloseHandle")

    def terminate(self, exit_code: int) -> None:
        if not self.handle:
            return

        result = self.kernel32.TerminateJobObject(
            self.handle,
            ctypes.c_uint32(exit_code),
        )
        if not result:
            _raise_last_error("TerminateJobObject")


class WindowsEnforcementAdapter:
    """Concrete Windows enforcement adapter backed by Job Objects."""

    def __init__(self) -> None:
        self._kernel32 = _load_kernel32()
        self._jobs: dict[int, _JobHandle] = {}

    @property
    def capabilities(self) -> EnforcementCapabilities:
        return EnforcementCapabilities(
            platform="windows",
            adapter_version=WINDOWS_ADAPTER_VERSION,
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

    def prepare(
        self,
        request: EnforcementRequest,
    ) -> PreparedEnforcement:
        policy: IsolationPolicy = request.policy

        raw_handle = self._kernel32.CreateJobObjectW(None, None)
        if not raw_handle:
            _raise_last_error("CreateJobObjectW")

        job = _JobHandle(int(raw_handle), self._kernel32)

        try:
            limit_info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            limit_info.BasicLimitInformation.LimitFlags = (
                JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            )

            if policy.process_limit is not None:
                limit_info.BasicLimitInformation.LimitFlags |= (
                    JOB_OBJECT_LIMIT_ACTIVE_PROCESS
                )
                limit_info.BasicLimitInformation.ActiveProcessLimit = (
                    policy.process_limit
                )

            if policy.memory_limit_bytes is not None:
                limit_info.BasicLimitInformation.LimitFlags |= (
                    JOB_OBJECT_LIMIT_PROCESS_MEMORY
                )
                limit_info.ProcessMemoryLimit = policy.memory_limit_bytes

            result = self._kernel32.SetInformationJobObject(
                job.handle,
                _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                ctypes.byref(limit_info),
                ctypes.sizeof(limit_info),
            )

            if not result:
                _raise_last_error("SetInformationJobObject")

            enforced = {
                EnforcementControl.FORCED_TERMINATION,
                EnforcementControl.DESCENDANT_CONTROL,
            }

            gaps: list[EnforcementGap] = [
                EnforcementGap(
                    EnforcementControl.FILESYSTEM_ISOLATION,
                    "Windows Job Objects do not provide filesystem isolation.",
                ),
                EnforcementGap(
                    EnforcementControl.NETWORK_ISOLATION,
                    "Network isolation is not implemented by this adapter.",
                ),
                EnforcementGap(
                    EnforcementControl.CREDENTIAL_ISOLATION,
                    "Credential isolation is not implemented by this adapter.",
                ),
            ]

            if policy.process_limit is not None:
                enforced.add(EnforcementControl.PROCESS_COUNT_LIMITS)
            else:
                gaps.append(
                    EnforcementGap(
                        EnforcementControl.PROCESS_COUNT_LIMITS,
                        "No process-count limit was requested by policy.",
                    )
                )

            if policy.memory_limit_bytes is not None:
                enforced.add(EnforcementControl.MEMORY_LIMITS)
            else:
                gaps.append(
                    EnforcementGap(
                        EnforcementControl.MEMORY_LIMITS,
                        "No memory limit was requested by policy.",
                    )
                )

            if policy.cpu_limit_percent is not None:
                cpu_info = _JOBOBJECT_CPU_RATE_CONTROL_INFORMATION()
                cpu_info.ControlFlags = (
                    JOB_OBJECT_CPU_RATE_CONTROL_ENABLE
                    | JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP
                )
                cpu_info.CpuRate = policy.cpu_limit_percent * 100

                result = self._kernel32.SetInformationJobObject(
                    job.handle,
                    _JOBOBJECT_CPU_RATE_CONTROL_INFORMATION,
                    ctypes.byref(cpu_info),
                    ctypes.sizeof(cpu_info),
                )

                if not result:
                    _raise_last_error(
                        "SetInformationJobObject(CPU)"
                    )

                enforced.add(EnforcementControl.CPU_LIMITS)
            else:
                gaps.append(
                    EnforcementGap(
                        EnforcementControl.CPU_LIMITS,
                        "No CPU limit was requested by policy.",
                    )
                )

            if policy.environment_allowlist:
                gaps.append(
                    EnforcementGap(
                        EnforcementControl.ENVIRONMENT_ISOLATION,
                        "Environment allowlisting is not implemented by this adapter.",
                    )
                )
            else:
                gaps.append(
                    EnforcementGap(
                        EnforcementControl.ENVIRONMENT_ISOLATION,
                        "No environment allowlist was requested by policy.",
                    )
                )

            plan = EnforcementPlan(
                platform="windows",
                adapter_version=WINDOWS_ADAPTER_VERSION,
                enforced_controls=frozenset(enforced),
                gaps=tuple(gaps),
                workspace_root=policy.workspace,
                network_enabled=False,
                environment=(),
            )

            prepared = PreparedEnforcement(
                handle_id=job.handle,
                plan=plan,
            )

            self._jobs[job.handle] = job
            return prepared

        except BaseException:
            job.close()
            raise

    def assign_process(
        self,
        prepared: PreparedEnforcement,
        process_handle: int,
    ) -> None:
        if isinstance(process_handle, bool) or not isinstance(
            process_handle,
            int,
        ):
            raise WindowsEnforcementError(
                "process_handle must be an integer native process handle"
            )

        if process_handle <= 0:
            raise WindowsEnforcementError(
                "process_handle must be a positive native process handle"
            )

        job = self._get_job(prepared)

        result = self._kernel32.AssignProcessToJobObject(
            job.handle,
            process_handle,
        )

        if not result:
            _raise_last_error("AssignProcessToJobObject")

    def terminate(
        self,
        prepared: PreparedEnforcement,
        *,
        exit_code: int = 1,
    ) -> None:
        if isinstance(exit_code, bool) or not isinstance(
            exit_code,
            int,
        ):
            raise WindowsEnforcementError(
                "exit_code must be an integer"
            )

        job = self._get_job(prepared)
        job.terminate(exit_code)

    def release(self, prepared: PreparedEnforcement) -> None:
        job = self._jobs.pop(prepared.handle_id, None)

        if job is None:
            return

        job.close()

    def _get_job(
        self,
        prepared: PreparedEnforcement,
    ) -> _JobHandle:
        job = self._jobs.get(prepared.handle_id)

        if job is None:
            raise WindowsEnforcementError(
                f"unknown or released enforcement handle: "
                f"{prepared.handle_id}"
            )

        return job
