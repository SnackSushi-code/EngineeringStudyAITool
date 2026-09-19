# ADR-0006: Configuration and Secret Separation

- Status: Accepted for Phase 0.3
- Date: 2026-09-19

## Decision
Separate ordinary configuration from secrets.

Ordinary configuration may be versioned when safe. Secrets must use protected storage or deployment-appropriate secret mechanisms.

Secrets must never be committed to source control, embedded in contracts, serialized into model-visible state, or written to ordinary application logs.

Adapters must declare required credential scope and purpose. Missing credentials fail closed for the affected operation.
