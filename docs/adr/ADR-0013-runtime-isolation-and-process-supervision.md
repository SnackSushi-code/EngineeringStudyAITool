# ADR-0013 — Runtime Isolation and Process Supervision

- Status: Proposed
- Phase: 0.4.6
- Date: 2026-09-19

## Context

Phase 0.4.5 contains adapter failures at the execution boundary, but an in-process worker that blocks indefinitely or terminates the interpreter cannot be forcibly isolated by exception handling alone.

Ann-E will eventually execute engineering, coding, research, security, and self-extension adapters. Some of these operations will involve third-party processes, external tools, generated code, or native libraries.

The runtime therefore needs a process-level boundary between the trusted orchestration runtime and privileged adapter execution.

## Decision

Introduce an explicit `ExecutionSupervisor` abstraction.

The supervisor owns:

- worker creation
- worker initialization
- IPC transport
- resource policy application
- lifecycle state
- cancellation
- timeout enforcement
- controlled termination
- process-exit observation
- result collection
- cleanup
- recovery classification

The core runtime does not directly execute privileged adapter worker code.

## Boundary

```text
Task Request
    |
    v
Orchestrator
    |
    v
Policy / Authorization
    |
    v
Adapter Execution Boundary
    |
    v
Execution Supervisor
    |
    +---- IPC ----> Isolated Adapter Worker
    |
    v
Validated Tool Result
```

## Required properties

1. Authorization occurs before worker creation.
2. Unknown adapters fail closed without spawning a worker.
3. Worker identity and task correlation are verified.
4. IPC messages are versioned and schema validated.
5. Timeout enforcement must eventually be able to terminate the isolated worker.
6. Worker crashes must not crash the core runtime.
7. Cleanup must be idempotent.
8. Results are untrusted until validated.
9. Resource controls must correspond to actual platform enforcement.
10. Platform-specific sandbox mechanisms must be isolated behind a policy/enforcement abstraction.

## Timeout semantics

Unlike Phase 0.4.5 cooperative/post-return timeout detection, Phase 0.4.6 introduces a supervisor-owned timeout boundary.

The supervisor must be able to:

1. observe deadline expiration,
2. request graceful shutdown,
3. wait for controlled exit,
4. forcibly terminate the isolated process when required,
5. classify the final result as `TIMED_OUT`,
6. clean up resources.

## Failure classification

At minimum:

- STARTUP_FAILED
- IPC_FAILED
- CANCELLED
- TIMED_OUT
- PROCESS_CRASHED
- RESOURCE_LIMIT
- MALFORMED_RESULT
- CLEANUP_FAILED

These classifications must not expose raw worker exception text to model-visible state.

## Alternatives rejected

### Thread-only isolation

Rejected because threads do not provide reliable process crash containment or forcible termination of arbitrary Python/native execution.

### In-process signal/exception handling

Rejected as the primary boundary because it does not create a sufficient failure boundary for arbitrary adapter code.

### One permanent worker process

Deferred as the default architecture because worker reuse introduces additional lifecycle, state contamination, and cleanup concerns.

## Consequences

Positive:

- Core runtime receives a stronger failure boundary.
- Timeouts can become enforceable.
- Worker crashes become containable.
- Platform sandboxing can evolve independently.
- Resource enforcement becomes explicit.

Costs:

- IPC complexity
- process startup overhead
- lifecycle management
- platform-specific enforcement work
- additional testing requirements

## Security note

A process boundary alone is not automatically a security sandbox. Filesystem, network, credential, process, and operating-system privilege controls must be explicitly enforced and tested.
