from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Protocol


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


class AdapterWorker(Protocol):
    manifest: AdapterManifest

    def execute(self, call, grant, cancellation):
        ...


class AdapterRegistry:
    """
    Adapter discovery and worker routing registry.

    This registry does NOT grant authorization.
    Authorization remains exclusively the responsibility of PolicyBroker.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._manifests: dict[str, AdapterManifest] = {}
        self._workers: dict[str, AdapterWorker] = {}

    def register(self, adapter: AdapterManifest | AdapterWorker) -> None:
        """
        Register adapter metadata or a concrete worker.

        Registering an adapter never creates authorization.
        """
        manifest = (
            adapter.manifest
            if hasattr(adapter, "manifest")
            else adapter
        )

        if not isinstance(manifest, AdapterManifest):
            raise TypeError("adapter must provide a valid AdapterManifest")

        with self._lock:
            if manifest.adapter_id in self._manifests:
                raise ValueError(
                    f"adapter already registered: {manifest.adapter_id}"
                )

            self._manifests[manifest.adapter_id] = manifest

            if hasattr(adapter, "execute"):
                self._workers[manifest.adapter_id] = adapter

    def unregister(self, adapter_id: str) -> None:
        with self._lock:
            self._manifests.pop(adapter_id, None)
            self._workers.pop(adapter_id, None)

    def get(self, adapter_id: str) -> AdapterManifest:
        """
        Return adapter metadata only.
        """
        with self._lock:
            if adapter_id not in self._manifests:
                raise KeyError(f"unknown adapter: {adapter_id}")
            return self._manifests[adapter_id]

    def get_worker(self, adapter_id: str) -> AdapterWorker | None:
        """
        Return the concrete worker for execution routing.

        This does NOT perform authorization.
        """
        with self._lock:
            return self._workers.get(adapter_id)

    def list(self) -> tuple[AdapterManifest, ...]:
        with self._lock:
            return tuple(
                self._manifests[k]
                for k in sorted(self._manifests)
            )

    def enabled(self) -> tuple[AdapterManifest, ...]:
        return tuple(
            item for item in self.list()
            if item.enabled
        )

    def validate(self) -> None:
        for manifest in self.list():
            if not manifest.adapter_id.startswith("anne."):
                raise ValueError(
                    "adapter IDs must use the 'anne.' namespace: "
                    f"{manifest.adapter_id}"
                )
