# Phase 0.2.1 — Machine-Readable Contract Schemas

## Objective
Make the Phase 0.2 contracts machine-validatable before runtime services are implemented.

## Contract families
- TaskRequest / TaskState
- ToolCall / ToolResult
- PermissionRequest / PermissionDecision
- Artifact
- Memory
- ColonyEvent
- SelfExtensionProposal
- Error

## Enforcement boundary
JSON Schema validates structure, required fields, types, enums, formats, and basic bounds. Runtime components must additionally enforce authorization, state-machine transitions, provenance truth, secret isolation, idempotency semantics, and fail-closed behavior.

## Compatibility
Schemas use Draft 2020-12 and a `schema_version` field. Breaking contract changes require a version increment and migration/compatibility tests as defined by Phase 0.2.
