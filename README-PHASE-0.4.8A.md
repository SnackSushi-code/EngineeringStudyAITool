# Phase 0.4.8-A â€” Platform Enforcement Contract

This package defines the platform-neutral contract for actual OS/platform security enforcement.

## Scope

Included:

- explicit enforcement capability model
- immutable enforcement request
- truthful enforcement plan
- explicit unenforced-control gaps
- preparation/release lifecycle contract
- regression tests preventing policy/enforcement confusion

Not included:

- Windows sandbox implementation
- Linux sandbox implementation
- macOS sandbox implementation
- network firewall implementation
- credential broker implementation
- OS process/job/container configuration
- resource-limit enforcement

A capability is not considered enforced merely because `IsolationPolicy` requests it.

## Acceptance

The next implementation phase must provide a concrete platform adapter whose reported controls correspond to real OS/platform mechanisms and dedicated enforcement tests.

## Development

Run from repository root:

```powershell
python -m pytest -q tests/runtime/test_platform_enforcement_contract.py
```
