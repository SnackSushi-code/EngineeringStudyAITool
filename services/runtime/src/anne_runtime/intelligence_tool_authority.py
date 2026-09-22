from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import uuid4

from .contracts import ToolCall
from .intelligence_contracts import IntelligenceToolProposal
from .tool_contracts import ToolContractError, ToolInvocation, ToolDescriptor
from .tool_registry import ToolRegistry


class ToolAuthorityError(ValueError):
    """Raised when a model tool proposal cannot be authorized."""


@dataclass(frozen=True)
class ResolvedToolCall:
    proposal: IntelligenceToolProposal
    descriptor: ToolDescriptor
    call: ToolCall


class ToolCapabilityCatalog:
    """Deterministic model-facing catalog without authority controls."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def snapshot(self) -> tuple[dict[str, object], ...]:
        entries = []
        for d in sorted(
            (self._registry.descriptor(t) for t in self._registry.ids()),
            key=lambda x: (x.tool_id, x.version),
        ):
            props = {}
            required = []
            for a in d.arguments.arguments:
                if a.required:
                    required.append(a.name)
                props[a.name] = {
                    "type": a.value_type.value,
                    "description": a.description,
                }
            entries.append(
                {
                    "tool_id": d.tool_id,
                    "version": d.version,
                    "description": d.description,
                    "capabilities": sorted(d.capabilities),
                    "arguments": {"required": sorted(required), "properties": props},
                }
            )
        return tuple(entries)

    def as_metadata_json(self) -> str:
        return json.dumps(self.snapshot(), separators=(",", ":"), sort_keys=True)


class ToolAuthorityResolver:
    """Derives executable authority only from the runtime ToolDescriptor."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def resolve(self, proposal: IntelligenceToolProposal) -> ResolvedToolCall:
        try:
            d = self._registry.descriptor(proposal.tool)
        except KeyError as exc:
            raise ToolAuthorityError(f"Unknown tool: {proposal.tool}") from exc
        try:
            d.arguments.validate(proposal.arguments)
            call = ToolCall(
                schema_version="1.0",
                request_id=proposal.request_id,
                task_id=proposal.task_id,
                tool=d.tool_id,
                operation=proposal.operation,
                arguments=dict(proposal.arguments),
                permissions=tuple(d.required_permissions),
                timeout_ms=d.max_timeout_ms,
                retry_mode=d.retry_mode,
                idempotency_key=str(uuid4()),
            )
            ToolInvocation(call, d)
        except (ToolContractError, ValueError) as exc:
            raise ToolAuthorityError(str(exc)) from exc
        return ResolvedToolCall(proposal, d, call)
