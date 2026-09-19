from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeConfig:
    environment: str = "development"
    workspace_root: Path = Path("./workspace")
    audit_path: Path = Path("./runtime-data/audit.jsonl")
    privileged_execution_enabled: bool = False
    network_enabled: bool = False
    self_update_enabled: bool = False

    def __post_init__(self) -> None:
        if self.privileged_execution_enabled:
            raise ValueError(
                "Phase 0.4.1 does not permit privileged execution. "
                "Enablement belongs to a later reviewed runtime milestone."
            )
