# Phase 0.4.8 — Windows Enforcement

## Objective

Provide real Windows-native enforcement for the Ann-E execution boundary.

## B2 — Job Object Enforcement

B2 introduces Windows Job Objects as the first concrete security mechanism.

The adapter now uses Windows-native Job Objects to enforce:

- forced termination;
- descendant-process containment;
- active process-count limits when requested;
- per-process memory limits when requested;
- CPU hard-cap limits when requested.

The adapter reports those controls as enforced only after the corresponding
Windows API configuration succeeds.

## Security boundary

Python multiprocessing is not treated as a security sandbox.

The Windows Job Object owns the worker process boundary and provides an
OS-enforced containment mechanism for the controls supported by B2.

`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` is enabled so that releasing the
supervisor's Job Object ownership cannot leave assigned worker processes
running outside the intended lifetime.

## Deferred controls

The following remain explicit enforcement gaps:

- filesystem isolation;
- network isolation;
- credential isolation;
- environment filtering at worker launch.

These controls must not be reported as enforced until their Windows-native
mechanisms are implemented and behaviorally tested.

## B2 acceptance criteria

1. Windows adapter imports and initializes successfully.
2. Job Object creation succeeds.
3. Job Object configuration succeeds for supported policy limits.
4. Forced termination is represented as an actual enforced capability.
5. Descendant-process containment is represented as an actual enforced capability.
6. Process-count limits are enforced when requested.
7. Memory limits are enforced when requested.
8. CPU hard caps are enforced when requested.
9. Deferred controls remain explicit gaps.
10. Job release is idempotent.
11. Non-Windows environments reject the Windows adapter.
12. Existing platform-enforcement contract tests continue to pass.

## Important implementation boundary

B2 prepares and owns the native Job Object but does not yet modify the
ExecutionSupervisor worker-launch sequence.

Supervisor integration remains a subsequent step so that process-handle
ownership and lifecycle transitions can be introduced with dedicated
end-to-end tests rather than hidden inside adapter preparation.
