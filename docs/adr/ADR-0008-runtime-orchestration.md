# ADR-0008 — Controlled Runtime Orchestration

## Status
Accepted for Phase 0.4.2.

## Decision
Introduce a single orchestration path that owns task lifecycle, validates ToolCalls, routes all permissions through the PolicyBroker, executes only through AuthorizedToolRunner/ToolExecutor, validates ToolResults, and records terminal outcomes in the audit log.

Cancellation is cooperative. The runtime will not pretend that a synchronous worker can be safely killed merely because an orchestration timer expired.

## Rationale
This makes the Phase 0.3 dependency direction executable and creates a narrow boundary for later engineering adapters. The no-op executor remains the only executor in this phase.

## Consequences
- Future adapters must honor the cancellation token.
- Future privileged workers must remain behind the same runner and policy boundary.
- Retry behavior must remain explicit and idempotent.
- Timeout tests cannot be interpreted as proof of process termination.
