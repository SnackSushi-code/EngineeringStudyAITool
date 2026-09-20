# Phase 0.4.8-A — Platform Enforcement Contract

## Objective

Define the contract that converts an authorized `IsolationPolicy` into a truthful, platform-specific enforcement plan.

## Boundary

```text
Policy Broker
     |
     | authorization
     v
Execution Supervisor
     |
     | EnforcementRequest
     v
PlatformEnforcementAdapter
     |
     | PreparedEnforcement
     v
Worker Process
```

The adapter is responsible for OS/platform enforcement. The policy broker remains responsible for authorization.

## Contract Objects

### EnforcementCapabilities

Reports controls a concrete adapter can actually enforce.

Controls include:

- process isolation
- forced termination
- filesystem isolation
- network isolation
- credential isolation
- memory limits
- CPU limits
- process-count limits
- descendant control
- environment isolation

### EnforcementRequest

Contains:

- execution ID
- request ID
- task ID
- worker descriptor
- requested `IsolationPolicy`

### EnforcementPlan

Contains:

- platform
- adapter version
- controls actually enforced
- explicit gaps for requested controls not enforced
- workspace root when applicable
- network state
- launch environment

An enforced control cannot simultaneously appear as an enforcement gap.

### PreparedEnforcement

Represents resources/configuration prepared for a later launch. It does not mean that the worker has started.

## Truthfulness Rule

The following distinction is mandatory:

```text
IsolationPolicy
    = requested constraint

EnforcementCapabilities
    = capability the adapter can actually enforce

EnforcementPlan.enforced_controls
    = controls this execution will actually receive

EnforcementPlan.gaps
    = requested controls not currently enforced
```

A boolean in policy configuration is never sufficient evidence of security enforcement.

## Platform Strategy

The contract is platform-neutral.

Phase 0.4.8-B will implement Windows enforcement first because Windows is the current development platform.

Linux and macOS implementations must be independently validated before equivalent capabilities are claimed.

## Explicitly Deferred

This phase does not implement:

- Windows Job Objects
- Windows restricted tokens
- Windows ACL/path enforcement
- Windows firewall/network isolation
- credential brokering
- descendant-process containment
- memory/CPU/process quotas
- supervisor launch integration

Those are implementation work for later Phase 0.4.8 subphases.
