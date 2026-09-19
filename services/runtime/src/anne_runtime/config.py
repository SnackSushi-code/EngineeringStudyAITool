from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


@dataclass(frozen=True)
class RuntimeConfig:
    environment: str = "development"
    workspace_root: Path = Path("./workspace")
    audit_path: Path = Path("./runtime-data/audit.jsonl")
    schema_dir: Path = Path("./packages/schemas")
    privileged_execution_enabled: bool = False
    network_enabled: bool = False
    self_update_enabled: bool = False

    def __post_init__(self) -> None:
        if self.privileged_execution_enabled:
            raise ValueError("Phase 0.4.3 does not permit privileged execution.")

    @classmethod
    def from_environment(cls) -> "RuntimeConfig":
        return cls(
            environment=os.getenv("ANN_E_ENVIRONMENT", "development"),
            workspace_root=Path(os.getenv("ANN_E_WORKSPACE_ROOT", "./workspace")),
            audit_path=Path(os.getenv("ANN_E_AUDIT_PATH", "./runtime-data/audit.jsonl")),
            schema_dir=Path(os.getenv("ANN_E_SCHEMA_DIR", "./packages/schemas")),
            privileged_execution_enabled=_env_bool("ANN_E_PRIVILEGED_EXECUTION", False),
            network_enabled=_env_bool("ANN_E_NETWORK_ENABLED", False),
            self_update_enabled=_env_bool("ANN_E_SELF_UPDATE_ENABLED", False),
        )
