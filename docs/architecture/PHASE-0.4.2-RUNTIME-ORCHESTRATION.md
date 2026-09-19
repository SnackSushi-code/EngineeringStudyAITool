# Phase 0.4.2 — Runtime Orchestration

## Objective
Implement the first controlled runtime path from a validated task request to a tool executor while preserving Phase 0.2 contracts and Phase 0.3 trust boundaries.

## Execution pipeline

```text
Task Request
  ↓
Task Orchestrator
  ↓
Task State Machine / Lifecycle
  ↓
Tool Call Validation
  ↓
Policy Broker
  ↓
Authorized Tool Runner
  ↓
Tool Executor
  ↓
Tool Result Validation
  ↓
Audit / Telemetry
```

There is exactly one controlled path from a `TaskRequest` to a `ToolExecutor` in the Phase 0.4 runtime.

## Guarantees
- `request_id` and `task_id` must remain correlated across the request/call/result path.
- Tool calls are schema-validated before authorization.
- Every declared permission scope is evaluated by the centralized policy broker.
- Any incomplete authorization prevents execution.
- The executor receives only the permissions represented by the ToolCall.
- Tool results are schema-validated before the task can succeed.
- Cancellation is cooperative and never relies on unsafe external process killing.
- SAFE retries require an explicit idempotency key and explicit retry policy.
- Timeout handling requests cooperative cancellation; an executor must honor the token.
- Terminal task states cannot reactivate.
- Audit records are written for terminal orchestration outcomes.

## Non-goals
- No shell execution.
- No unrestricted filesystem access.
- No credentials.
- No network execution.
- No real engineering-tool adapters.
- No model provider calls.
- No self-update.
- No Colony authority.

## Failure behavior
Authorization failure is terminal `DENIED`. Cooperative cancellation is terminal `CANCELLED`. An execution timeout is terminal `TIMED_OUT` and requests cancellation. Validation or unexpected runtime failures become `FAILED`.

The runtime does not claim that a timeout forcibly terminates a worker. Real workers must implement cooperative cancellation before privileged execution is enabled.
