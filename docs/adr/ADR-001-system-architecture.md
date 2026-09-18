# ADR-001: Modular Agent Platform

**Status:** Accepted baseline

## Decision

Ann-E will use a modular service/agent architecture with explicit contracts and adapters. The model layer is separated from tool execution.

## Why

Ann-E must eventually integrate engineering software, security tooling, learning systems and a Colony environment. Strong boundaries reduce coupling and make individual components replaceable and testable.

## Consequences

Positive:
- provider independence
- easier testing
- smaller security blast radius
- replaceable integrations
- clear ownership of state

Tradeoff:
- more interfaces and infrastructure than a single-process prototype
