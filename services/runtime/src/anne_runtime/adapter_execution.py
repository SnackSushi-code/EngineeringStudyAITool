from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .adapters import AdapterManifest, AdapterRegistry
from .cancellation import CancellationToken
from .contracts import TaskState, ToolCall, ToolResult
from .errors import RuntimeInvariantError


@dataclass(frozen=True)
class ResourceGrant:
    workspace: Path
    network_enabled: bool = False
    process_enabled: bool = False
    timeout_seconds: int = 30


@dataclass(frozen=True)
class ArtifactProvenance:
    adapter_id: str
    adapter_version: str
    operation: str
    truth_state: str
    generated_by_task: str


@dataclass(frozen=True)
class AdapterArtifact:
    artifact_id: str
    path: str
    media_type: str
    provenance: ArtifactProvenance


@dataclass(frozen=True)
class AdapterResult:
    request_id: str
    task_id: str
    adapter_id: str
    operation: str
    status: TaskState
    artifacts: tuple[AdapterArtifact, ...] = ()
    message: str = ""


class AdapterExecutionBoundary:
    """
    Controlled boundary between authorized runtime execution
    and engineering adapter workers.

    Capability declaration, adapter discovery, and authorization
    remain separate concerns.
    """

    def __init__(self, registry: AdapterRegistry, policy_broker) -> None:
        self._registry = registry
        self._policy_broker = policy_broker

    def execute(
        self,
        call: ToolCall,
        authorization,
        grant: ResourceGrant,
        cancellation: CancellationToken,
    ) -> ToolResult:
        cancellation.throw_if_requested()

        if not authorization:
            raise RuntimeInvariantError(
                "Adapter execution requires authorization"
            )

        adapter_id = call.tool

        try:
            manifest = self._registry.get(adapter_id)
        except KeyError as exc:
            raise RuntimeInvariantError(
                f"Unknown adapter: {adapter_id}"
            ) from exc

        if not manifest.enabled:
            raise RuntimeInvariantError(
                f"Adapter is disabled: {adapter_id}"
            )

        if call.operation not in manifest.operations:
            raise RuntimeInvariantError(
                f"Unsupported adapter operation: "
                f"{adapter_id}.{call.operation}"
            )

        worker = self._registry.get_worker(adapter_id)

        if worker is None:
            raise RuntimeInvariantError(
                f"No execution worker registered for adapter: {adapter_id}"
            )

        cancellation.throw_if_requested()

        result = worker.execute(
            call,
            grant,
            cancellation,
        )

        if result.request_id != call.request_id:
            raise RuntimeInvariantError(
                "Adapter result request correlation mismatch"
            )

        if result.task_id != call.task_id:
            raise RuntimeInvariantError(
                "Adapter result task correlation mismatch"
            )

        if result.adapter_id != adapter_id:
            raise RuntimeInvariantError(
                "Adapter result identity mismatch"
            )

        if result.operation != call.operation:
            raise RuntimeInvariantError(
                "Adapter result operation mismatch"
            )

        artifact_records = tuple(
            artifact.path
            for artifact in result.artifacts
        )

        validation_checks = tuple(
            {
                "check": "adapter_boundary_correlation",
                "status": "PASSED",
            },
        )

        return ToolResult(
            schema_version="0.2",
            request_id=call.request_id,
            task_id=call.task_id,
            status=result.status,
            result={
                "adapter_id": result.adapter_id,
                "operation": result.operation,
                "message": result.message,
                "artifacts": [
                    {
                        "artifact_id": artifact.artifact_id,
                        "path": artifact.path,
                        "media_type": artifact.media_type,
                        "truth_state": artifact.provenance.truth_state,
                        "adapter_id": artifact.provenance.adapter_id,
                        "adapter_version": artifact.provenance.adapter_version,
                    }
                    for artifact in result.artifacts
                ],
            },
            artifacts=artifact_records,
            validation_state="GENERATED",
            validation_checks=validation_checks,
            tool=call.tool,
            tool_version=manifest.version,
            adapter_version=manifest.version,
            error=None,
            logs=(
                f"Adapter {adapter_id}.{call.operation} completed.",
            ),
        )


class MockEngineeringAdapter:
    """
    Deterministic adapter used only for runtime boundary tests.
    """

    manifest = AdapterManifest(
        adapter_id="anne.mock.engineering",
        display_name="Ann-E Mock Engineering Adapter",
        version="0.1.0",
        runtime_api="0.4",
        operations=("generate_artifact",),
        enabled=True,
    )

    def execute(
        self,
        call: ToolCall,
        grant: ResourceGrant,
        cancellation: CancellationToken,
    ) -> AdapterResult:
        cancellation.throw_if_requested()

        artifact = AdapterArtifact(
            artifact_id=f"{call.task_id}:mock-artifact",
            path=str(grant.workspace / "mock-artifact.txt"),
            media_type="text/plain",
            provenance=ArtifactProvenance(
                adapter_id=self.manifest.adapter_id,
                adapter_version=self.manifest.version,
                operation=call.operation,
                truth_state="GENERATED",
                generated_by_task=str(call.task_id),
            ),
        )

        return AdapterResult(
            request_id=call.request_id,
            task_id=call.task_id,
            adapter_id=self.manifest.adapter_id,
            operation=call.operation,
            status=TaskState.SUCCEEDED,
            artifacts=(artifact,),
            message="Deterministic mock engineering artifact generated.",
        )
