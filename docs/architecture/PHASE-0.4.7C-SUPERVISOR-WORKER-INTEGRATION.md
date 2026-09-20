# Phase 0.4.7-C — Supervisor/Worker Integration

## Purpose

Turn the Phase 0.4.7-A lifecycle foundation and Phase 0.4.7-B worker process into one controlled execution path.

## Execution sequence

```text
AUTHORIZED
    |
    v
STARTING -> WorkerProcess.start(START)
    |
    v
READY <- READY validated for worker/request/task/sequence
    |
    v
RUNNING -> WorkerProcess.execute(EXECUTE)
    |
    +--> RESULT -> COMPLETED -> CLEANUP -> TERMINAL
    |
    +--> TIMEOUT -> TIMING_OUT -> TERMINATING -> CLEANUP -> TERMINAL
    |
    +--> FAILURE -> CRASHED/TERMINATING -> CLEANUP -> TERMINAL
```

## Authority

The supervisor owns lifecycle state. The worker owns only its process-local handler execution and IPC loop. A worker cannot grant itself authorization.

## Timeout

A response deadline is enforced by the supervisor integration. When the worker does not respond before the deadline, the integration transitions through timeout recovery and terminates the worker. The current process termination is direct-worker termination; descendant control is intentionally deferred to platform enforcement.

## Cancellation

Cancellation is cooperative when the worker can receive the CANCEL message. If the worker is blocked inside its handler and cannot service CANCEL, the integration falls back to process termination. This prevents a cancelled execution from silently remaining active.

## Cleanup invariant

Every execution returned by `SupervisedExecution.execute()` is in `TERMINAL` state. Worker IPC is closed and the integration removes its worker reference after cleanup.

## Telemetry

When configured, the integration emits correlated events for authorization, start, ready, running, completion, failure/recovery, cancellation, and cleanup. Event payloads pass through the existing telemetry redaction boundary.

## Phase boundary

This is process supervision, not a security sandbox. Platform-specific enforcement remains incomplete until Phase 0.4.8 independently demonstrates filesystem, network, credential, resource, and descendant-process controls.
