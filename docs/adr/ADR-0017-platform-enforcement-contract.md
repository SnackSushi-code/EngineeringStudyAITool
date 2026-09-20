# ADR-0017 — Platform Enforcement Contract

## Status

Accepted for Phase 0.4.8-A.

## Decision

Introduce a platform-neutral `PlatformEnforcementAdapter` contract between the execution supervisor and OS-specific security enforcement.

The contract distinguishes:

1. requested isolation policy,
2. platform capabilities,
3. controls actually enforced,
4. controls that remain unenforced,
5. prepared enforcement resources.

A platform adapter MUST NOT report a control as enforced unless its implementation actually applies the control and tests demonstrate that behavior.

## Rationale

The existing `IsolationPolicy` deliberately represents requested constraints rather than enforcement. Treating policy fields as security controls would create a false security boundary.

The new contract makes enforcement claims explicit and reviewable before Windows-specific implementation begins.

## Consequences

Positive:

- prevents policy/enforcement confusion
- supports Windows/Linux/macOS adapters without changing supervisor contracts
- makes unsupported controls explicit
- enables security regression tests against concrete enforcement mechanisms

Negative:

- additional abstraction and validation work
- platform implementations must prove their capabilities independently
- some policies may remain partially enforceable depending on OS facilities

## Security Rules

- default-deny remains authoritative in the policy broker
- authorization is separate from platform enforcement
- preparation does not mean the worker has started
- release must be idempotent
- credentials must not be inherited implicitly
- network access must not be described as isolated unless isolation is actually enforced
- platform parity must not be assumed
