# ADR-0011 — Adapter Execution Boundary

## Decision
All external engineering/tool integrations execute through a dedicated adapter execution boundary.

The registry describes adapters. The policy broker authorizes operations. The execution boundary enforces the authorization snapshot and resource grant. An adapter cannot authorize itself.

## Rationale
This keeps integration code replaceable and prevents future KiCad, MATLAB, LabVIEW, CAD, simulation, or other tooling from becoming a privileged path around the runtime security model.

## Consequences
- real adapters must implement the common contract
- adapter capabilities are descriptive, not permissions
- execution requires correlation identifiers
- adapter results require correlation and identity checks before becoming runtime results
- failure normalization is a subsequent runtime hardening stage
- sandbox/process isolation can evolve independently of adapter implementations
