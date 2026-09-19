# ADR-0010 — Runtime Configuration and Observability

## Status
Accepted for Phase 0.4.3.

## Decision
Use typed operational configuration, environment-based loading, structured telemetry events, and health checks. Secrets remain outside configuration and telemetry.

## Rationale
Production systems need deterministic configuration and diagnostics without creating a second path around the security model.

## Consequences
Configuration is testable, telemetry has stable event names/correlation fields, and health checks can identify missing infrastructure before integration execution.
