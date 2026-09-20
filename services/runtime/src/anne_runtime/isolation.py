from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PlatformCapabilities:
    """Capabilities actually reported by a platform enforcement adapter."""

    process_isolation: bool = False
    forced_termination: bool = False
    filesystem_isolation: bool = False
    network_isolation: bool = False
    credential_isolation: bool = False
    memory_limits: bool = False
    cpu_limits: bool = False
    process_count_limits: bool = False
    descendant_control: bool = False


@dataclass(frozen=True)
class IsolationPolicy:
    """Requested isolation policy; not enforcement by itself."""

    workspace: Path
    timeout_seconds: float
    memory_limit_bytes: int | None = None
    cpu_limit_percent: int | None = None
    process_limit: int | None = None
    read_only_paths: tuple[Path, ...] = ()
    writable_paths: tuple[Path, ...] = ()
    network_enabled: bool = False
    environment_allowlist: tuple[str, ...] = ()
    credential_ids: tuple[str, ...] = ()
    max_message_bytes: int = 1_048_576
    max_result_bytes: int = 4_194_304
    max_artifact_bytes: int = 16_777_216

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.memory_limit_bytes is not None and self.memory_limit_bytes <= 0:
            raise ValueError("memory_limit_bytes must be positive")
        if self.cpu_limit_percent is not None and not 1 <= self.cpu_limit_percent <= 100:
            raise ValueError("cpu_limit_percent must be between 1 and 100")
        if self.process_limit is not None and self.process_limit <= 0:
            raise ValueError("process_limit must be positive")
        if self.max_message_bytes <= 0 or self.max_result_bytes <= 0 or self.max_artifact_bytes <= 0:
            raise ValueError("message/result/artifact limits must be positive")


@dataclass(frozen=True)
class WorkerDescriptor:
    worker_id: str
    adapter_id: str
    adapter_version: str
    runtime_api: str

    def __post_init__(self) -> None:
        for name, value in (
            ("worker_id", self.worker_id),
            ("adapter_id", self.adapter_id),
            ("adapter_version", self.adapter_version),
            ("runtime_api", self.runtime_api),
        ):
            if not value.strip():
                raise ValueError(f"{name} cannot be empty")
