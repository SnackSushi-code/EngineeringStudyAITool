"""Windows platform enforcement foundation.

Phase 0.4.8-B1 establishes the concrete Windows adapter boundary.

Important security property:
    This module does NOT claim OS security controls that are not yet
    actually enforced.

Later phases will attach concrete Windows mechanisms such as Job Objects,
filesystem ACL enforcement, resource quotas, credential isolation, and
supervisor launch integration.
"""

from __future__ import annotations

import os



from uuid import uuid4

from .platform_enforcement import (
    EnforcementCapabilities,
    EnforcementControl,
    EnforcementGap,
    EnforcementPlan,
    EnforcementRequest,
    PreparedEnforcement,
)


WINDOWS_ADAPTER_VERSION = "0.1.0"


class WindowsEnforcementError(RuntimeError):
    """Raised when Windows enforcement preparation cannot be completed."""


class WindowsEnforcementAdapter:
    """Concrete Windows enforcement adapter foundation.

    B1 deliberately reports zero enforced security controls.

    This is intentional. A process boundary created by Python
    multiprocessing is not itself a Windows security sandbox, and no
    Windows-native security mechanism is claimed here until its behavior
    is implemented and regression-tested.
    """

    _UNSUPPORTED_REASON = (
        "Windows enforcement mechanism is not implemented in Phase 0.4.8-B1"
    )

    def __init__(self) -> None:
        if os.name != "nt":
            raise WindowsEnforcementError(
                "WindowsEnforcementAdapter requires Windows."
            )

    @property
    def capabilities(self) -> EnforcementCapabilities:
        """Return only capabilities actually enforceable by this adapter.

        B1 intentionally returns an empty capability set.
        """

        return EnforcementCapabilities(
            platform="windows",
            adapter_version=WINDOWS_ADAPTER_VERSION,
            controls=frozenset(),
        )

    def prepare(self, request: EnforcementRequest) -> PreparedEnforcement:
        """Prepare a truthful Windows enforcement plan.

        Preparation allocates no worker and does not claim that the worker
        has started or that deferred security mechanisms are active.
        """

        policy = request.policy
        gaps: list[EnforcementGap] = []

        requested_controls = self._requested_controls(policy)

        for control in requested_controls:
            gaps.append(
                EnforcementGap(
                    control=control,
                    reason=self._UNSUPPORTED_REASON,
                )
            )

        plan = EnforcementPlan(
            platform="windows",
            adapter_version=WINDOWS_ADAPTER_VERSION,
            enforced_controls=frozenset(),
            gaps=tuple(gaps),
            workspace_root=policy.workspace,
            network_enabled=False,
            environment={},
        )

        return PreparedEnforcement(
            handle_id=f"windows-prepared-{uuid4()}",
            plan=plan,
        )

    def release(self, prepared: PreparedEnforcement) -> None:
        """Release preparation resources.

        B1 owns no native Windows resources yet, so release is intentionally
        idempotent and has no side effects.
        """

        if not isinstance(prepared, PreparedEnforcement):
            raise TypeError("prepared must be PreparedEnforcement")

    @staticmethod
    def _requested_controls(policy: object) -> tuple[EnforcementControl, ...]:
        """Translate policy constraints into requested enforcement controls.

        This function describes requested controls only. It never upgrades
        them into enforced controls.
        """

        controls: list[EnforcementControl] = []

        workspace = getattr(policy, "workspace", None)
        if workspace is not None:
            controls.append(EnforcementControl.FILESYSTEM_ISOLATION)

        read_only_paths = getattr(policy, "read_only_paths", ())
        writable_paths = getattr(policy, "writable_paths", ())
        if read_only_paths or writable_paths:
            if EnforcementControl.FILESYSTEM_ISOLATION not in controls:
                controls.append(EnforcementControl.FILESYSTEM_ISOLATION)

        network_enabled = getattr(policy, "network_enabled", False)
        if not network_enabled:
            controls.append(EnforcementControl.NETWORK_ISOLATION)

        if getattr(policy, "credential_ids", ()):
            controls.append(EnforcementControl.CREDENTIAL_ISOLATION)

        if getattr(policy, "memory_limit_bytes", None) is not None:
            controls.append(EnforcementControl.MEMORY_LIMITS)

        if getattr(policy, "cpu_limit_percent", None) is not None:
            controls.append(EnforcementControl.CPU_LIMITS)

        if getattr(policy, "process_limit", None) is not None:
            controls.append(EnforcementControl.PROCESS_COUNT_LIMITS)

        if getattr(policy, "environment_allowlist", None):
            controls.append(EnforcementControl.ENVIRONMENT_ISOLATION)

        return tuple(dict.fromkeys(controls))
