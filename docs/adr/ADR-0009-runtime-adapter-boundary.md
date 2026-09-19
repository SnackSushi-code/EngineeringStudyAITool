# ADR-0009 — Runtime Adapter Boundary

## Status
Accepted for Phase 0.4.3.

## Decision
Introduce a central adapter registry and explicit adapter manifest contract. The registry provides discovery and metadata only; it is not an authorization authority and cannot execute operations.

## Rationale
Engineering integrations have different APIs, versions, installation states, and failure modes. A stable adapter boundary prevents vendor-specific behavior from leaking into orchestration.

## Consequences
Every integration has explicit identity/version metadata, is independently testable, and remains behind the existing policy/execution boundary.
