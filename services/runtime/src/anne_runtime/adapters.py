from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True)
class AdapterManifest:
    adapter_id: str
    display_name: str
    version: str
    runtime_api: str
    operations: tuple[str, ...] = ()
    enabled: bool = False

    def __post_init__(self) -> None:
        if not self.adapter_id.strip():
            raise ValueError("adapter_id cannot be empty")
        if not self.display_name.strip():
            raise ValueError("display_name cannot be empty")
        if not self.version.strip() or not self.runtime_api.strip():
            raise ValueError("version and runtime_api cannot be empty")
        if any(not operation.strip() for operation in self.operations):
            raise ValueError("adapter operations cannot be empty")


class AdapterRegistry:
    """Metadata registry only; never grants execution authority."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._adapters: dict[str, AdapterManifest] = {}

    def register(self, manifest: AdapterManifest) -> None:
        with self._lock:
            if manifest.adapter_id in self._adapters:
                raise ValueError(f"adapter already registered: {manifest.adapter_id}")
            self._adapters[manifest.adapter_id] = manifest

    def unregister(self, adapter_id: str) -> None:
        with self._lock:
            self._adapters.pop(adapter_id, None)

    def get(self, adapter_id: str) -> AdapterManifest:
        with self._lock:
            if adapter_id not in self._adapters:
                raise KeyError(f"unknown adapter: {adapter_id}")
            return self._adapters[adapter_id]

    def list(self) -> tuple[AdapterManifest, ...]:
        with self._lock:
            return tuple(self._adapters[k] for k in sorted(self._adapters))

    def enabled(self) -> tuple[AdapterManifest, ...]:
        return tuple(item for item in self.list() if item.enabled)

    def validate(self) -> None:
        for manifest in self.list():
            if not manifest.adapter_id.startswith("anne."):
                raise ValueError(
                    f"adapter IDs must use the 'anne.' namespace: {manifest.adapter_id}"
                )
