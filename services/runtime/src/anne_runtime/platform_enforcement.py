from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Mapping, Protocol
from uuid import UUID

from .isolation import IsolationPolicy, WorkerDescriptor


class EnforcementContractError(ValueError):
    """Raised when an enforcement request or plan violates the contract."""


class EnforcementControl(StrEnum):
    PROCESS_ISOLATION = "PROCESS_ISOLATION"
    FORCED_TERMINATION = "FORCED_TERMINATION"
    FILESYSTEM_ISOLATION = "FILESYSTEM_ISOLATION"
    NETWORK_ISOLATION = "NETWORK_ISOLATION"
    CREDENTIAL_ISOLATION = "CREDENTIAL_ISOLATION"
    MEMORY_LIMITS = "MEMORY_LIMITS"
    CPU_LIMITS = "CPU_LIMITS"
    PROCESS_COUNT_LIMITS = "PROCESS_COUNT_LIMITS"
    DESCENDANT_CONTROL = "DESCENDANT_CONTROL"
    ENVIRONMENT_ISOLATION = "ENVIRONMENT_ISOLATION"


@dataclass(frozen=True)
class EnforcementCapabilities:
    """Capabilities an adapter can actually enforce on its target platform.

    A declared capability is a contract claim and must be backed by platform
    implementation and tests before it is reported as enforced.
    """

    platform: str
    adapter_version: str
    controls: frozenset[EnforcementControl]

    def supports(self, control: EnforcementControl) -> bool:
        return control in self.controls

    def __post_init__(self) -> None:
        if not self.platform.strip():
            raise EnforcementContractError("platform cannot be empty")
        if not self.adapter_version.strip():
            raise EnforcementContractError("adapter_version cannot be empty")


@dataclass(frozen=True)
class EnforcementRequest:
    """Immutable request presented to a platform enforcement adapter."""

    execution_id: UUID
    request_id: UUID
    task_id: UUID
    worker: WorkerDescriptor
    policy: IsolationPolicy

    def __post_init__(self) -> None:
        if self.execution_id.int == 0:
            raise EnforcementContractError("execution_id cannot be nil")
        if self.request_id.int == 0:
            raise EnforcementContractError("request_id cannot be nil")
        if self.task_id.int == 0:
            raise EnforcementContractError("task_id cannot be nil")


@dataclass(frozen=True)
class EnforcementGap:
    """A requested control that is not currently enforced by the adapter."""

    control: EnforcementControl
    reason: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise EnforcementContractError("enforcement gap reason cannot be empty")


@dataclass(frozen=True)
class EnforcementPlan:
    """A truthful, pre-execution description of enforceable controls.

    `enforced_controls` must contain only controls the adapter will actually
    apply. Requested-but-unenforced controls must appear in `gaps`.
    """

    platform: str
    adapter_version: str
    enforced_controls: frozenset[EnforcementControl]
    gaps: tuple[EnforcementGap, ...] = ()
    workspace_root: Path | None = None
    network_enabled: bool = False
    environment: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.platform.strip():
            raise EnforcementContractError("plan platform cannot be empty")
        if not self.adapter_version.strip():
            raise EnforcementContractError("plan adapter_version cannot be empty")
        if self.network_enabled and EnforcementControl.NETWORK_ISOLATION not in self.enforced_controls:
            raise EnforcementContractError(
                "network_enabled requires enforced NETWORK_ISOLATION"
            )
        gap_controls = {gap.control for gap in self.gaps}
        if gap_controls & set(self.enforced_controls):
            raise EnforcementContractError(
                "a control cannot be both enforced and listed as a gap"
            )

    def is_enforced(self, control: EnforcementControl) -> bool:
        return control in self.enforced_controls


@dataclass(frozen=True)
class PreparedEnforcement:
    """Opaque preparation handle owned by the platform adapter.

    The handle does not imply that a worker has started. It only represents
    resources/configuration prepared for a later supervised launch.
    """

    handle_id: str
    plan: EnforcementPlan

    def __post_init__(self) -> None:
        if not self.handle_id.strip():
            raise EnforcementContractError("handle_id cannot be empty")


class PlatformEnforcementAdapter(Protocol):
    """Platform-neutral enforcement contract.

    Implementations belong to platform-specific packages. The adapter must
    never report a control as enforced unless the platform operation actually
    applies it and its behavior is covered by tests.
    """

    @property
    def capabilities(self) -> EnforcementCapabilities:
        ...

    def prepare(self, request: EnforcementRequest) -> PreparedEnforcement:
        """Prepare an isolated launch without starting the worker."""
        ...

    def assign_process(
        self,
        prepared: PreparedEnforcement,
        process_handle: int,
    ) -> None:
        """Attach the created worker process to the prepared boundary."""
        ...

    def terminate(
        self,
        prepared: PreparedEnforcement,
        *,
        exit_code: int = 1,
    ) -> None:
        """Force termination of processes governed by the boundary."""
        ...

    def release(self, prepared: PreparedEnforcement) -> None:
        """Release all preparation resources; must be idempotent."""
        ...
