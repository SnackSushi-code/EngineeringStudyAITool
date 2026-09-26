# Phase 0.4.4 — Runtime Adapter Execution Boundary

## Objective
Create one controlled path from an authorized tool call to an adapter worker without allowing adapter metadata, capabilities, or external tools to become policy authorities.

## Invariants
1. Adapter declarations never grant permission.
2. Unknown adapters fail closed.
3. Unknown operations fail closed.
4. Execution requires an authorization snapshot from the runtime boundary.
5. Adapter workers receive only the resources explicitly supplied by the execution boundary.
6. Adapter results are checked for required correlation and identity invariants before becoming runtime results.
7. Domain artifact validation is a subsequent validation stage; generated artifacts remain GENERATED until an actual validator runs.
8. Artifacts carry provenance and truth state.
9. The mock adapter is deterministic and performs no external I/O.
10. Real engineering integrations remain future adapters behind this boundary.

## Flow
Task Request -> Orchestrator -> Policy Broker -> Adapter Registry -> Execution Boundary -> Adapter Worker -> Result Validation -> Artifact/Telemetry/Audit

## Resource policy
The execution boundary accepts a narrow immutable resource grant containing workspace path, network allowance, process allowance, and timeout. This grant is descriptive input to a future sandbox implementation; it is not an authorization mechanism by itself.

## Artifact truth
Generated artifacts begin at GENERATED. Validation may advance them to PARSED or VALIDATED only when the corresponding validator actually ran. Simulation and experimental verification require explicit future integrations.

## Failure containment
Timeout, cancellation, adapter exception, malformed result, unknown adapter, and unauthorized execution are terminally represented without leaking secrets or arbitrary exception details into model-visible state.
