# Phase 0.4.6 â€” Runtime Isolation and Process Supervision

## 1. Objective

Create a trusted runtime/supervisor boundary around privileged adapter execution.

Authorization determines whether an operation may execute.
Isolation determines where and under what enforceable resource and security boundary the authorized operation may execute.

## 2. Trust zones

### Zone A â€” Core Runtime

Trusted components:

- orchestrator
- policy broker
- task state machine
- audit
- contracts
- observability

### Zone B â€” Execution Supervisor

Controlled security boundary:

- process creation
- resource policy
- IPC
- lifecycle
- termination
- cleanup

### Zone C â€” Adapter Worker

Untrusted execution zone:

- adapter implementation
- third-party libraries
- external engineering tools
- generated code
- model-produced execution plans

The worker must not be treated as trusted merely because its adapter manifest is registered.

## 3. Lifecycle

```text
AUTHORIZED
    |
    v
STARTING
    |
    v
READY
    |
    v
RUNNING
    |
    +--> CANCELLING --> TERMINATING --> CLEANUP
    |
    +--> TIMING_OUT --> TERMINATING --> CLEANUP
    |
    +--> CRASHED ---------------------> CLEANUP
    |
    +--> COMPLETED --------------------> CLEANUP
```

No terminal state may transition back into execution.

## 4. Supervisor responsibilities

The supervisor must:

- validate an authorized execution request
- construct a minimal worker environment
- apply an explicit resource policy
- create the worker
- establish authenticated/correlated IPC
- enforce a deadline
- propagate cancellation
- terminate the worker when required
- collect only bounded results
- validate worker identity
- classify failures
- clean up temporary resources
- emit structured lifecycle telemetry

## 5. IPC

IPC messages must include:

- protocol version
- request ID
- task ID
- worker ID
- message type
- sequence number
- payload

The protocol must reject:

- unknown protocol versions
- mismatched request/task IDs
- invalid message types
- invalid sequence numbers
- oversized messages
- malformed payloads

## 6. Resource policy

The contract should represent, at minimum:

- timeout
- memory limit
- CPU limit where enforceable
- process-count limit where enforceable
- workspace root
- read-only paths
- writable paths
- network enabled/disabled
- environment allowlist
- credential availability
- maximum output/artifact size

A policy value is not considered an enforcement mechanism until the platform adapter actually applies and tests it.

## 7. Filesystem

Workers receive an explicit workspace.

The supervisor must not assume that a worker honoring a path restriction is sufficient. Enforcement must occur at the process/platform boundary where available.

## 8. Network

Network access defaults to disabled.

Enabling network requires:

1. explicit authorization,
2. explicit resource policy,
3. platform enforcement,
4. audit record.

## 9. Credentials

Credentials must never be inherited from the parent environment by default.

Secrets must be brokered explicitly and scoped to the operation.

## 10. Recovery

Recovery must be deterministic:

```text
worker crash
    -> mark execution failed
    -> capture bounded diagnostics
    -> terminate descendants where enforceable
    -> clean temporary resources
    -> emit audit event
    -> return safe ToolResult
```

## 11. Required regression tests

- denied authorization does not spawn a worker
- unknown adapter does not spawn a worker
- worker startup failure is contained
- worker crash is contained
- malformed IPC is rejected
- request correlation mismatch is rejected
- task correlation mismatch is rejected
- timeout terminates a worker
- cancellation terminates a worker
- oversized result is rejected
- workspace escape is rejected
- disabled network is enforced
- cleanup is idempotent
- worker descendants are handled according to platform capability
- core runtime remains alive after worker failure

## 12. Platform strategy

The supervisor interface is platform-neutral.

Enforcement adapters may differ by operating system.

The architecture must not claim identical sandbox strength across Windows, Linux, and macOS until each implementation is independently validated.

## 13. Phase boundary

This architecture package defines the contract. Actual OS-level sandbox enforcement is implementation work and must not be represented as complete until tests demonstrate it.
