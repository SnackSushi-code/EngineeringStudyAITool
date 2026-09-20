# ADR-0016 — Supervisor-to-Worker Integration

## Status
Accepted for Phase 0.4.7-C.

## Decision
`ExecutionSupervisor` is the authoritative lifecycle controller for worker-process execution. `SupervisedExecution` is the integration layer that connects the supervisor state machine to `WorkerProcess`.

The integration owns:

- authorization before worker creation;
- START/READY handshake;
- RUNNING transition before EXECUTE;
- worker response correlation validation;
- timeout recovery;
- cancellation recovery;
- deterministic termination and cleanup;
- structured runtime telemetry.

A caller does not decide independently whether a timed-out worker may continue. Timeout recovery transitions the supervised execution into recovery and terminates the worker process.

## Non-goals

This ADR does not claim:

- OS-level sandboxing;
- filesystem isolation;
- network isolation;
- credential isolation;
- descendant-process containment;
- memory/CPU enforcement.

Those require platform enforcement adapters and tests in Phase 0.4.8.

## Failure semantics

Failures are converted into stable result codes without exposing raw exception text:

- `WORKER_TIMEOUT`
- `WORKER_CANCELLED`
- `WORKER_EXECUTION_FAILED`

The supervisor always reaches cleanup and a terminal supervisor state before returning from the integration path.
