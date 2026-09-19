# Phase 0.4.5 — Runtime Hardening and Failure Containment

## Objective

Harden the Phase 0.4.4 adapter boundary so ordinary adapter failures become safe, structured terminal runtime results without leaking exception details or accepting malformed artifact metadata.

## Invariants

1. Adapter exceptions are normalized into structured terminal failures.
2. Adapter timeout failures are normalized into `TIMED_OUT` results.
3. Cooperative cancellation propagates and is not converted into an adapter failure.
4. Malformed adapter results are rejected and normalized.
5. Adapter result correlation must match the originating request/task.
6. Adapter identity and operation must match the registered manifest and ToolCall.
7. Adapter result status must be terminal.
8. Artifact provenance must match adapter, version, operation, and task.
9. Artifact paths must remain inside the granted workspace.
10. Model-visible failure messages contain safe generic text rather than raw exception messages.
11. Generated artifacts remain `GENERATED` until a real domain validator runs.
12. Preemptive termination of arbitrary worker code is not claimed; cooperative cancellation remains the current execution model.

## Failure flow

Task Request -> Orchestrator -> Policy Broker -> Adapter Registry -> Execution Boundary -> Adapter Worker -> Failure/Result Containment -> Runtime Result -> Artifact/Telemetry/Audit

## Timeout semantics

The orchestrator already provides a cooperative task timeout. The adapter boundary additionally converts adapter-raised `TimeoutError` and post-return grant-time overruns into terminal `TIMED_OUT` results.

A worker that ignores cancellation cannot safely be killed by the current in-process runtime. Process isolation is a later hardening stage.

## Security properties

- Unknown adapters and operations still fail closed.
- Authorization is still required before execution.
- Resource grants are not authorization.
- Artifact paths cannot escape the granted workspace.
- Raw exception messages are not surfaced in model-visible error messages.
- Adapter provenance cannot claim another adapter or task.

## Validation

The phase adds focused regression tests for:
- exception normalization;
- timeout normalization;
- malformed results;
- artifact path escape;
- cancellation propagation;
- positive timeout configuration.
