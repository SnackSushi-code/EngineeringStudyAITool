# Ann-E Phase 0.4.7-A — Execution Supervisor Foundation

## Purpose
Implement the first executable layer of the Phase 0.4.6 runtime-isolation architecture.

## Explicit boundary
This increment does **not** claim OS-level isolation, subprocess enforcement, network sandboxing, filesystem sandboxing, or forced process termination. Those capabilities belong to later 0.4.7 increments and must be demonstrated by tests.

## Deliverables
- `execution_supervisor.py`: lifecycle state machine, authorization-before-start invariant, terminal-state protection, bounded-result configuration, deterministic cleanup.
- `isolation.py`: typed isolation/resource policy, worker descriptor, platform capability declaration.
- `worker_protocol.py`: versioned IPC envelope, identity/correlation, sequence and message-size validation.
- Architecture and runtime tests.

## Next increment
Phase 0.4.7-B will add the first concrete worker-process startup/readiness implementation.
