# ADR-0014 — Execution Supervisor Foundation

- Status: Proposed
- Phase: 0.4.7-A

## Context
Phase 0.4.6 established a process-level isolation architecture but intentionally left the supervisor implementation for the next phase.

## Decision
Introduce typed supervisor primitives:
- `IsolationPolicy`
- `PlatformCapabilities`
- `WorkerDescriptor`
- `SupervisorState`
- `SupervisorExecution`
- `WorkerMessage`
- `ExecutionSupervisor`

The supervisor owns lifecycle state and validates boundary conditions required before a future worker process can be created.

## Security invariants
1. Authorization must exist before a worker may be started.
2. Unknown or invalid worker descriptors fail closed.
3. Terminal executions cannot return to execution.
4. Worker identity and task/request correlation are mandatory.
5. IPC messages are versioned and bounded.
6. Isolation policy values are configuration until a platform adapter enforces them.
7. Cleanup is idempotent.

## Explicit non-goals
This ADR does not implement OS-level sandboxing, subprocess creation, forced process termination, network isolation, filesystem isolation, or credential brokering.
