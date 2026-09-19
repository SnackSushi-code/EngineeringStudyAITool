# ADR-0012 — Runtime Failure Containment

## Decision

Adapter execution failures must be contained at the adapter execution boundary before they become model-visible runtime state.

The boundary distinguishes:

- authorization/configuration failures, which remain runtime invariant failures;
- cooperative cancellation, which propagates to the orchestrator;
- adapter timeouts, which become terminal `TIMED_OUT` results;
- adapter exceptions, which become sanitized terminal `FAILED` results;
- malformed adapter results or unsafe artifact metadata, which become sanitized terminal `FAILED` results.

Exception text is never copied into model-visible error messages.

## Rationale

External engineering integrations are untrusted execution components. A faulty or compromised adapter must not be able to:

- crash the orchestration process through an ordinary exception;
- expose arbitrary exception text or secrets;
- return non-terminal task states;
- forge correlation or adapter identity;
- claim artifact provenance for another task/adapter;
- publish an artifact outside its granted workspace.

## Scope

Phase 0.4.5 establishes failure containment and result integrity checks. It does not provide preemptive thread/process termination for arbitrary third-party code. Cooperative cancellation remains the required mechanism for running workers.

Deeper process sandboxing and hard isolation remain subsequent runtime/security work.
