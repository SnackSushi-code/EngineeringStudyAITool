# Phase 0.4.8-C ? Supervisor Enforcement Integration

## Purpose

Phase 0.4.8-C connects the execution supervisor to the platform enforcement
boundary established by Phase 0.4.8-A and implemented for Windows in
Phase 0.4.8-B.

## Execution sequence

The supervisor now enforces the following ordering:

1. Authorization succeeds.
2. Platform enforcement is prepared.
3. Supervisor transitions to STARTING.
4. Worker process is created.
5. Native process handle becomes available.
6. Platform adapter receives the native process handle.
7. Platform assignment is attempted.
8. Worker receives its START protocol message.
9. Worker reaches READY.
10. Execution may proceed.

The platform assignment callback occurs inside `WorkerProcess.start()` between
`process.start()` and `_send(start_message)`.

Preparation therefore does not imply that the worker has started.

## Failure handling

If platform assignment fails:

- the worker is terminated,
- enforcement resources are released,
- the supervisor enters CLEANUP,
- the execution reaches TERMINAL.

If execution times out:

- supervisor enters TIMING_OUT,
- platform enforcement termination is requested,
- worker termination is requested.

## Cleanup

Cleanup is idempotent and releases both worker and platform resources.

The supervisor closes worker IPC resources after terminating the worker and
releases the prepared enforcement handle.

## Compatibility

The enforcement adapter remains optional.

If no enforcement adapter is supplied, the supervisor retains the existing
worker lifecycle behavior while continuing to use the same authorization and
state-machine boundaries.

## Truthfulness

The supervisor does not claim filesystem, network, credential, environment,
or other controls independently.

Those controls remain the responsibility of the platform enforcement adapter.
