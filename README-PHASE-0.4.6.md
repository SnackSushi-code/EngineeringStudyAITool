# Ann-E Phase 0.4.6 — Runtime Isolation and Process Supervision

## Purpose

Phase 0.4.6 establishes the architecture and contracts for executing privileged adapters outside the Ann-E core runtime process.

This phase is intentionally split into:

1. Architecture and contracts
2. Supervisor implementation
3. Platform-specific enforcement
4. Security and failure testing

The first deliverable establishes the boundary before implementation.

## Security invariant

Authorization answers:

> May Ann-E perform this operation?

Isolation answers:

> Where and under what enforceable resource/security boundary may it execute?

An adapter must never be able to grant itself authorization.

## Scope

- Process-level adapter boundary
- Supervisor lifecycle model
- Versioned IPC contract
- Explicit isolation state model
- Resource-limit contract
- Controlled termination contract
- Crash containment contract
- Workspace/network/process policy representation
- Threat-model updates
- Architecture regression tests

## Explicit non-goals for this architecture package

- No production subprocess implementation yet
- No claim of cross-platform hard sandboxing before platform enforcement is implemented
- No arbitrary command execution
- No unrestricted filesystem access
- No unrestricted network access
- No automatic privilege escalation

## Next implementation stage

Implement the supervisor against these contracts, then add platform-specific enforcement and failure-injection tests.
