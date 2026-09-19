# ADR-0005: Process Boundaries and Privilege Separation

- Status: Accepted for Phase 0.3
- Date: 2026-09-19

## Context
Ann-E will eventually interact with engineering software, code execution environments, files, networks, and self-update mechanisms. Separate runtime boundaries improve failure containment and privilege separation.

## Decision
Use separate logical runtime boundaries for:
1. desktop presentation;
2. orchestration;
3. security/policy;
4. tool/integration workers;
5. Colony visualization/simulation.

These may initially run as local processes/services rather than distributed services.

## Consequences
Positive: smaller privilege domains, clearer failure containment, easier testing, safer integrations, clearer audit ownership.

Negative: IPC complexity, lifecycle management, serialization overhead, and more diagnostics.

The logical security boundary remains even if two components temporarily share a development process.
