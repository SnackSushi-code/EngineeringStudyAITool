# Ann-E Phase 0 Completion Gate

## Purpose

Phase 0 establishes the production foundation required before Phase 1 begins.

The completion gate requires:

1. Runtime architecture and contracts are present.
2. Execution authorization remains separate from enforcement.
3. Worker execution has an explicit supervisor boundary.
4. Windows process enforcement uses a native Job Object.
5. Platform enforcement reports only controls actually configured by the adapter.
6. Unsupported controls remain explicit enforcement gaps.
7. Enforcement assignment occurs before worker execution is released.
8. Timeout and cleanup paths request platform termination.
9. Runtime tests, enforcement integration tests, compilation, and repository hygiene pass.
10. Local and remote commit state are verified before Phase 0 is declared complete.

## Windows enforcement scope

The Phase 0 Windows adapter provides:

- Job Object ownership for worker processes.
- forced termination through Job Object termination;
- descendant-process containment through Job Object membership;
- optional active-process limits when requested by policy;
- optional per-process memory limits when requested by policy;
- optional CPU hard-cap limits when requested by policy.

The adapter does not claim:

- filesystem isolation;
- network isolation;
- credential isolation;
- environment isolation.

Those remain explicit gaps until implemented and behaviorally tested.

## Supervisor integration

The supervisor sequence is:

1. authorization;
2. enforcement preparation;
3. worker process creation;
4. native process-handle acquisition;
5. platform enforcement assignment;
6. worker start-message delivery;
7. READY state;
8. execution.

Preparation alone never implies that a worker has started.

If platform assignment fails, the supervisor terminates and closes the worker, releases enforcement, enters cleanup, and reaches a terminal cleanup-complete state.

If execution times out, the supervisor enters `TIMING_OUT`, requests platform termination, then requests worker termination.

## Validation requirements

The Phase 0 gate must pass:

- Python compilation;
- supervisor/enforcement integration tests;
- Windows enforcement platform smoke tests;
- full runtime test suite;
- `git diff --check`;
- allowed-file change review;
- exact local/remote commit verification.

Phase 1 must not depend on an unverified or dirty Phase 0 baseline.
