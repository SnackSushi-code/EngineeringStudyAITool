# ADR-0007: Observability and Audit Ownership

- Status: Accepted for Phase 0.3
- Date: 2026-09-19

## Decision
Ann-E distinguishes:
- operational telemetry;
- protected diagnostics;
- security audit records.

Audit records must support reconstruction of who/what initiated an action, task/request identity, requested operation, policy decision, target/scope, result, artifact references, and timestamps.

Sensitive values must be redacted. Application components may append audit records but may not rewrite prior audit history.
