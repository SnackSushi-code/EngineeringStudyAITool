# Phase 0.4.7-B — Worker Process & IPC

## Purpose

Implement the first real worker-process boundary described by Phase 0.4.6 and
the Phase 0.4.7-A supervisor foundation.

## Implemented

- Real Python worker process using the `spawn` multiprocessing context.
- Explicit START/READY/EXECUTE/RESULT/CANCEL/SHUTDOWN/ERROR protocol handling.
- JSON-framed IPC payloads over a multiprocessing connection.
- Maximum IPC message size enforcement.
- Request/task/worker correlation checks.
- Monotonic sequence enforcement for the worker lifecycle.
- Startup handshake.
- Bounded response waits.
- Process crash detection when the worker exits before a response.
- Graceful shutdown followed by forced process termination when the worker does
  not exit within the configured grace period.
- Deterministic cleanup primitives.
- Unit tests for successful IPC, timeout detection, malformed protocol input,
  and worker identity mismatch.

## Security boundary

This phase establishes a **process boundary**, not a complete OS security
sandbox.

It does not yet claim:

- filesystem isolation;
- network isolation;
- credential isolation;
- memory/CPU/process-count enforcement;
- descendant-process containment;
- cross-platform sandbox equivalence.

Those require platform-specific enforcement work in the subsequent isolation
phases.

## Timeout semantics

A worker IPC timeout is detected by the supervisor. The caller may then invoke
`terminate()`.

`terminate()` attempts a bounded graceful SHUTDOWN first and then uses the
platform's process termination primitive if the worker remains alive.

This is intentionally stronger than the earlier cooperative timeout model:
the supervisor no longer has to trust an in-process worker to return.

## IPC invariants

Every accepted worker message must have:

1. the current protocol version;
2. the expected worker identity;
3. the expected request ID;
4. the expected task ID;
5. a non-negative sequence;
6. a valid message type;
7. a JSON-object payload within the configured byte limit.

Unexpected messages or correlation failures put the worker wrapper into a
failed/crashed state rather than being silently accepted.

## Explicit non-goals

This phase does not connect arbitrary shell commands, unrestricted filesystem
access, credentials, network access, or arbitrary AI-generated code execution
to the worker process.
