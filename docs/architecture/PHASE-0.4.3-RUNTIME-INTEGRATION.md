# Phase 0.4.3 — Runtime Integration & Production Scaffolding

## Objective
Add the minimum production scaffolding needed before real engineering adapters are introduced.

## Adapter boundary
Adapters declare identity, version, runtime API, supported operations, and enabled state. The registry provides discovery and metadata only. It is never an authorization mechanism and cannot execute operations.

Future adapters remain behind the existing PolicyBroker and AuthorizedToolRunner.

## Observability boundary
Runtime components emit structured events with stable names and optional request/task correlation. Payloads are redacted before persistence. Observability cannot authorize execution.

## Configuration boundary
Operational settings are loaded from explicit environment variables and safe defaults. Secrets are excluded. Privileged execution remains forbidden in this phase.

## Health boundary
Health checks report schema availability, audit-directory readiness, and adapter-registry integrity. Health is informational and cannot alter security policy.

## Invariants
1. Adapter registration cannot grant permission.
2. Adapter metadata cannot contain credentials.
3. Observability cannot authorize operations.
4. Configuration cannot enable privileged execution in Phase 0.4.3.
5. Health checks cannot mutate security policy.
6. The Phase 0.4.2 controlled execution path remains intact.
7. External integrations remain replaceable adapters.
8. Unknown adapters fail closed at lookup.
