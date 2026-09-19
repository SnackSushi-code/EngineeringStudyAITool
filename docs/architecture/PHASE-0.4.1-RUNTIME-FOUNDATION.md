# Phase 0.4.1 — Runtime Foundation

## Status

Implementation baseline for the first executable Ann-E runtime layer.

## Objective

Turn the Phase 0.2 contracts and Phase 0.3 trust boundaries into executable, testable runtime primitives without introducing privileged external execution.

## Runtime flow

```text
TaskRequest
    |
    v
Contract Validation
    |
    v
Task State Machine
    |
    +----> Agent/Planner proposal
    |
    v
Permission Broker
    |
    +---- DENY / REQUIRE_APPROVAL
    |
    v
Scoped Tool Interface
    |
    v
ToolResult
    |
    v
Artifact / Validation metadata
    |
    v
Audit
```

## Components

### Contract layer

Typed dataclasses represent stable contract objects. The runtime also validates dictionaries against the Phase 0.2 JSON Schemas.

Schema validation is not authorization.

### Task state machine

The state machine enforces the Phase 0.2 lifecycle.

Non-terminal:
- QUEUED
- PLANNING
- WAITING_APPROVAL
- RUNNING
- VALIDATING
- ROLLING_BACK

Terminal:
- SUCCEEDED
- FAILED
- CANCELLED
- DENIED
- TIMED_OUT

Terminal states cannot transition to any other state.

### Permission broker

The broker is fail-closed.

- Unknown permission classes are denied by the typed boundary.
- Missing policy rules are denied.
- Approval is represented separately from ALLOW.
- The broker never executes tools.
- A tool receives only the permissions that were explicitly requested and authorized.

### Audit

Audit events are written as JSON Lines.

Each record includes a previous-record hash and a canonical record hash. This provides tamper evidence for the application-owned log.

Production deployments must place the audit store behind a stronger ownership boundary; this class is not itself a secure storage service.

### Secret redaction

The runtime applies conservative redaction to credential-like keys before ordinary serialization.

This is defense in depth and does not replace protected secret storage.

### Tool interface

`ToolExecutor` is an execution boundary, not an execution implementation.

Phase 0.4.1 provides `NoopToolExecutor` for integration tests. It performs no external operation.

## Security invariants implemented

1. Agents cannot directly authorize operations.
2. Policy denial is fail-closed.
3. Tool execution requires complete authorization.
4. A worker cannot expand the permission set supplied to it.
5. Secret-like values are redacted before ordinary audit serialization.
6. Terminal tasks cannot become active again.
7. The runtime does not provide arbitrary OS execution.

## Acceptance criteria

- Runtime package imports without network access.
- Contract objects validate against Phase 0.2 schemas.
- Task transitions reject invalid transitions.
- Terminal-state transitions are rejected.
- Permission broker denies by default.
- Approval requirements are explicit.
- Tool calls cannot execute without authorization.
- Audit records are append-only through the application API.
- Audit records are hash-chained.
- Secret-like values are redacted.
- Failure paths are covered by automated tests.
