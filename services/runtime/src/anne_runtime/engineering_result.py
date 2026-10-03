from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
from uuid import UUID

from .contracts import TaskState, ToolResult


@dataclass(frozen=True)
class EngineeringQuantity:
    """A semantic engineering value with explicitly known or unknown units."""

    value: Any
    unit: str | None = None
    dimension: str | None = None
    unit_source: str = "unknown"

    def __post_init__(self) -> None:
        if self.unit_source not in {"explicit", "contract", "unknown"}:
            raise ValueError(
                "unit_source must be one of: explicit, contract, unknown"
            )

        if self.unit is None and self.unit_source != "unknown":
            raise ValueError(
                "unit_source must be 'unknown' when unit is not provided"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "unit": self.unit,
            "dimension": self.dimension,
            "unit_source": self.unit_source,
        }


@dataclass(frozen=True)
class EngineeringProvenance:
    """Runtime provenance preserved across an engineering handoff."""

    tool: str
    tool_version: str
    adapter_version: str

    def to_dict(self) -> dict[str, str]:
        return {
            "tool": self.tool,
            "tool_version": self.tool_version,
            "adapter_version": self.adapter_version,
        }


@dataclass(frozen=True)
class EngineeringValidation:
    """Validation state preserved from the runtime ToolResult."""

    state: str
    checks: tuple[Mapping[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "checks": [dict(check) for check in self.checks],
        }


@dataclass(frozen=True)
class EngineeringHandoff:
    """
    Domain-level engineering handoff produced from a successful ToolResult.

    ToolResult remains the runtime execution contract. This object adds
    engineering semantics without changing the runtime security boundary.
    """

    schema_version: str
    request_id: UUID
    task_id: UUID
    status: TaskState
    source_tool: str
    operation: str
    values: Mapping[str, Any]
    quantities: Mapping[str, EngineeringQuantity]
    artifacts: tuple[str, ...]
    validation: EngineeringValidation
    provenance: EngineeringProvenance
    error: Mapping[str, Any] | None = None

    @classmethod
    def from_tool_result(
        cls,
        result: ToolResult,
        *,
        operation: str,
        quantities: Mapping[str, EngineeringQuantity] | None = None,
    ) -> "EngineeringHandoff":
        if not isinstance(result, ToolResult):
            raise TypeError("result must be a ToolResult")

        if not operation.strip():
            raise ValueError("operation must not be empty")

        normalized_quantities = dict(quantities or {})

        unknown_quantity_names = (
            set(normalized_quantities) - set(result.result)
        )
        if unknown_quantity_names:
            raise ValueError(
                "Engineering quantities reference values not present in "
                f"ToolResult: {sorted(unknown_quantity_names)}"
            )

        return cls(
            schema_version="1.0",
            request_id=result.request_id,
            task_id=result.task_id,
            status=result.status,
            source_tool=result.tool,
            operation=operation,
            values=dict(result.result),
            quantities=normalized_quantities,
            artifacts=tuple(result.artifacts),
            validation=EngineeringValidation(
                state=result.validation_state,
                checks=tuple(result.validation_checks),
            ),
            provenance=EngineeringProvenance(
                tool=result.tool,
                tool_version=result.tool_version,
                adapter_version=result.adapter_version,
            ),
            error=dict(result.error) if result.error is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "request_id": str(self.request_id),
            "task_id": str(self.task_id),
            "status": self.status.value,
            "source_tool": self.source_tool,
            "operation": self.operation,
            "values": dict(self.values),
            "quantities": {
                name: quantity.to_dict()
                for name, quantity in self.quantities.items()
            },
            "artifacts": list(self.artifacts),
            "validation": self.validation.to_dict(),
            "provenance": self.provenance.to_dict(),
            "error": dict(self.error) if self.error is not None else None,
        }
