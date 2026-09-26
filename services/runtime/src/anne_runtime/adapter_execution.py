from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import monotonic

from .adapters import AdapterManifest, AdapterRegistry
from .cancellation import CancellationRequested, CancellationToken
from .contracts import TaskState, ToolCall, ToolResult
from .errors import RuntimeInvariantError


_VALID_TRUTH_STATES = frozenset(
    {
        "GENERATED",
        "PARSED",
        "VALIDATED",
        "SIMULATED",
        "EXPERIMENTALLY_VERIFIED",
    }
)

_TERMINAL_STATES = frozenset(
    {
        TaskState.SUCCEEDED,
        TaskState.FAILED,
        TaskState.CANCELLED,
        TaskState.DENIED,
        TaskState.TIMED_OUT,
    }
)


@dataclass(frozen=True)
class ResourceGrant:
    workspace: Path
    network_enabled: bool = False
    process_enabled: bool = False
    timeout_seconds: int = 30

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


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
    Controlled boundary between authorized execution and adapter workers.

    Capability declaration, adapter discovery, authorization, and failure
    containment remain separate concerns.
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
        started = monotonic()

        try:
            result = worker.execute(call, grant, cancellation)
        except CancellationRequested:
            raise
        except TimeoutError:
            return self._failure_result(
                call,
                manifest,
                code="ANN_E_ADAPTER_TIMEOUT",
                message="Adapter execution exceeded its allowed time.",
                retryable=True,
            )
        except Exception as exc:
            return self._failure_result(
                call,
                manifest,
                code="ANN_E_ADAPTER_FAILURE",
                message="Adapter execution failed.",
                retryable=False,
                details={"exception_type": type(exc).__name__},
            )

        cancellation.throw_if_requested()

        if monotonic() - started > grant.timeout_seconds:
            return self._failure_result(
                call,
                manifest,
                code="ANN_E_ADAPTER_TIMEOUT",
                message="Adapter execution exceeded its allowed time.",
                retryable=True,
            )

        try:
            self._validate_adapter_result(
                result,
                call,
                manifest,
                grant,
            )
        except RuntimeInvariantError:
            return self._failure_result(
                call,
                manifest,
                code="ANN_E_ADAPTER_MALFORMED_RESULT",
                message="Adapter returned an invalid result.",
                retryable=False,
            )

        artifact_records = tuple(
            artifact.path
            for artifact in result.artifacts
        )

        validation_checks = (
            {
                "check": "adapter_boundary_correlation",
                "status": "PASSED",
            },
            {
                "check": "adapter_identity",
                "status": "PASSED",
            },
            {
                "check": "artifact_workspace_containment",
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

    @staticmethod
    def _validate_adapter_result(
        result: AdapterResult,
        call: ToolCall,
        manifest: AdapterManifest,
        grant: ResourceGrant,
    ) -> None:
        if not isinstance(result, AdapterResult):
            raise RuntimeInvariantError(
                "Adapter returned an unsupported runtime result type"
            )

        if result.request_id != str(call.request_id):
            raise RuntimeInvariantError(
                "Adapter result request correlation mismatch"
            )
        if result.task_id != str(call.task_id):
            raise RuntimeInvariantError(
                "Adapter result task correlation mismatch"
            )
        if result.adapter_id != manifest.adapter_id:
            raise RuntimeInvariantError(
                "Adapter result identity mismatch"
            )
        if result.operation != call.operation:
            raise RuntimeInvariantError(
                "Adapter result operation mismatch"
            )
        if result.status not in _TERMINAL_STATES:
            raise RuntimeInvariantError(
                "Adapter result status is not terminal"
            )

        workspace = grant.workspace.resolve()

        for artifact in result.artifacts:
            if not isinstance(artifact, AdapterArtifact):
                raise RuntimeInvariantError(
                    "Adapter returned an unsupported artifact type"
                )

            if not artifact.artifact_id or not artifact.media_type:
                raise RuntimeInvariantError(
                    "Adapter artifact metadata is incomplete"
                )

            provenance = artifact.provenance
            if not isinstance(provenance, ArtifactProvenance):
                raise RuntimeInvariantError(
                    "Adapter artifact provenance is malformed"
                )

            if provenance.adapter_id != manifest.adapter_id:
                raise RuntimeInvariantError(
                    "Adapter artifact provenance identity mismatch"
                )

            if provenance.adapter_version != manifest.version:
                raise RuntimeInvariantError(
                    "Adapter artifact provenance version mismatch"
                )

            if provenance.operation != call.operation:
                raise RuntimeInvariantError(
                    "Adapter artifact provenance operation mismatch"
                )

            if provenance.truth_state not in _VALID_TRUTH_STATES:
                raise RuntimeInvariantError(
                    "Adapter artifact truth state is unsupported"
                )

            if provenance.generated_by_task != str(call.task_id):
                raise RuntimeInvariantError(
                    "Adapter artifact task provenance mismatch"
                )

            artifact_path = Path(artifact.path).resolve()
            try:
                artifact_path.relative_to(workspace)
            except ValueError as exc:
                raise RuntimeInvariantError(
                    "Adapter artifact path escapes the granted workspace"
                ) from exc

    @staticmethod
    def _failure_result(
        call: ToolCall,
        manifest: AdapterManifest,
        *,
        code: str,
        message: str,
        retryable: bool,
        details: dict[str, str] | None = None,
    ) -> ToolResult:
        error = {
            "code": code,
            "message": message,
            "retryable": retryable,
            "details": details or {},
        }

        return ToolResult(
            schema_version="0.2",
            request_id=call.request_id,
            task_id=call.task_id,
            status=(
                TaskState.TIMED_OUT
                if code == "ANN_E_ADAPTER_TIMEOUT"
                else TaskState.FAILED
            ),
            result={},
            artifacts=(),
            validation_state="FAILED",
            validation_checks=(
                {
                    "check": "adapter_failure_containment",
                    "status": "PASSED",
                },
            ),
            tool=call.tool,
            tool_version=manifest.version,
            adapter_version=manifest.version,
            error=error,
            logs=(
                f"Adapter {call.tool}.{call.operation} failed safely.",
            ),
        )


class MockEngineeringAdapter:
    """Deterministic adapter used only for runtime boundary tests."""

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
            request_id=str(call.request_id),
            task_id=str(call.task_id),
            adapter_id=self.manifest.adapter_id,
            operation=call.operation,
            status=TaskState.SUCCEEDED,
            artifacts=(artifact,),
            message="Deterministic mock engineering artifact generated.",
        )
