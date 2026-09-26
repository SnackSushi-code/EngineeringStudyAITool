# Phase 0.4.6 Isolation Threat Model

## Assets

- Ann-E core runtime integrity
- user files
- credentials
- engineering project files
- audit records
- generated artifacts
- network access
- system resources

## Threats

### T1 — Adapter process crash

Impact: core runtime instability.

Control: separate worker process and supervisor-owned lifecycle.

### T2 — Infinite or excessive execution

Impact: denial of service.

Control: supervisor-owned deadline and enforced termination.

### T3 — Workspace escape

Impact: unauthorized file modification.

Control: explicit workspace policy plus platform enforcement.

### T4 — Unauthorized network access

Impact: data exfiltration or unintended external actions.

Control: network-disabled default plus explicit enforcement.

### T5 — Credential inheritance

Impact: secret disclosure.

Control: sanitized worker environment and credential broker.

### T6 — Malformed worker output

Impact: corrupted runtime state.

Control: versioned IPC and strict schema validation.

### T7 — Worker impersonation

Impact: accepting output from the wrong process.

Control: worker identity/correlation validation and authenticated IPC where supported.

### T8 — Resource exhaustion

Impact: system or runtime denial of service.

Control: explicit resource policy and platform enforcement.

### T9 — Cleanup failure

Impact: orphaned processes/resources.

Control: idempotent cleanup and post-termination reconciliation.

## Security invariant

A worker is never trusted merely because it was selected by the adapter registry.

Authorization, isolation, validation, and audit remain separate controls.
