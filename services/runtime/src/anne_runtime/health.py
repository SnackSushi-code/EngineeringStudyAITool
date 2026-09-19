from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .adapters import AdapterRegistry
from .config import RuntimeConfig


@dataclass(frozen=True)
class HealthCheck:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class RuntimeHealth:
    ok: bool
    checks: tuple[HealthCheck, ...]


def check_runtime_health(config: RuntimeConfig, adapters: AdapterRegistry) -> RuntimeHealth:
    checks = [
        HealthCheck("schema-directory", config.schema_dir.is_dir(), str(config.schema_dir)),
    ]

    audit_parent: Path = config.audit_path.parent
    try:
        audit_parent.mkdir(parents=True, exist_ok=True)
        audit_ok = True
    except OSError:
        audit_ok = False
    checks.append(HealthCheck("audit-parent", audit_ok, str(audit_parent)))

    try:
        adapters.validate()
        checks.append(HealthCheck("adapter-registry", True, "valid"))
    except Exception as exc:
        checks.append(HealthCheck("adapter-registry", False, type(exc).__name__))

    return RuntimeHealth(ok=all(check.ok for check in checks), checks=tuple(checks))
