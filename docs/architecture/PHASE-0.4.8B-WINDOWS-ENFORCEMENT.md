# Phase 0.4.8-B1 — Windows Enforcement Foundation

## Objective

Introduce the first concrete Windows implementation of the platform
enforcement contract defined by Phase 0.4.8-A.

## Security Principle

B1 intentionally makes **zero security enforcement capability claims**.

The adapter is concrete and Windows-specific, but it does not report a
control as enforced until a Windows-native mechanism is actually applied
and dedicated tests demonstrate that behavior.

This prevents the Python worker process boundary from being mistaken for a
security sandbox.

## Adapter

Implementation:

services/runtime/src/anne_runtime/windows_enforcement.py

The adapter:

- is Windows-specific;
- implements the Phase 0.4.8-A platform enforcement contract;
- reports zero enforced controls in B1;
- converts requested policy constraints into explicit enforcement gaps;
- does not claim Job Object, filesystem, network, credential, resource,
  environment, or descendant-process enforcement;
- provides idempotent release behavior.

## B1 Boundary

B1 does not yet implement:

- Windows Job Objects;
- restricted tokens;
- filesystem ACL enforcement;
- network isolation;
- credential isolation;
- memory limits;
- CPU limits;
- process-count limits;
- descendant-process containment;
- supervisor launch integration.

Those mechanisms are intentionally deferred to subsequent enforcement
phases.

## Acceptance Criteria

B1 is complete only when:

1. The Windows adapter imports successfully on Windows.
2. The adapter exposes the Phase 0.4.8-A enforcement contract.
3. No control is reported as enforced without a real Windows mechanism.
4. Requested policy constraints produce explicit enforcement gaps.
5. Release is safe to call repeatedly.
6. Dedicated Windows adapter tests pass.
7. Existing platform-enforcement contract tests continue to pass.
8. No supervisor behavior is changed by B1.
