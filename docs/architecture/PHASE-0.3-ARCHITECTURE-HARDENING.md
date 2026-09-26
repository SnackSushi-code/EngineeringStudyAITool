# Phase 0.3 — Architecture Hardening

## Status
Proposed implementation baseline for Phase 0.3.

## Objective
Convert the accepted Phase 0.1/0.2 architecture decisions into enforceable repository-level rules before application runtime implementation begins.

The goal is not to implement the desktop application yet. The goal is to make incorrect architecture difficult to introduce.

## Existing foundation
Phase 0.1 establishes:
- Tauri 2 + React + TypeScript for the desktop shell.
- Three.js for the embedded 3D Ann-E widget.
- Godot 4 as a separate Colony visualization/simulation process.
- Python for orchestration and engineering automation.
- Rust only where native security, OS integration, or performance justify it.
- SQLite as the initial storage implementation.
- Adapter-per-tool integration.
- Centralized policy enforcement.
- Model-provider abstraction.
- Isolated self-extension workflow.

Phase 0.2 establishes:
- versioned machine-readable contracts;
- task, tool, permission, artifact, memory, Colony, self-extension, and error contracts;
- fail-closed permission semantics;
- provenance and validation-state requirements;
- explicit idempotency and cancellation expectations.

## Phase 0.3 principles
1. Presentation never becomes a privileged execution layer.
2. Agents propose; policy authorizes.
3. Workers execute only within explicit scopes.
4. Secrets never enter model-visible state.
5. Colony is an operational visualization/simulation client, never an authority.
6. Artifacts carry provenance and validation truth.
7. Configuration is separate from secrets.
8. Audit records are append-only from application components.
9. External frameworks remain replaceable adapters.
10. New capabilities must have an explicit owner, contract, permission model, and test strategy.

## Trust zones

### Zone A — Presentation
Owns React UI, desktop interaction, Ann-E widget, user-facing state, sanitized telemetry, and Colony presentation.

Forbidden:
- arbitrary process execution;
- unrestricted filesystem access;
- direct credential access;
- direct engineering-tool control;
- policy bypass.

### Zone B — Orchestration
Owns task lifecycle, planning, agent routing, model gateway, workflow state, memory retrieval, tool scheduling, and approval coordination.

Forbidden:
- direct privileged OS access;
- silent permission elevation;
- bypassing the policy broker.

### Zone C — Tool/Integration Workers
Owns engineering adapters, code execution workers, and Git/GitHub adapters.

Every worker receives task ID, explicit permission scope, artifact references, timeout/resource limits, and cancellation signal.

Every worker returns structured result, artifact references, validation state, provenance, safe error information, and logs.

### Zone D — Security/Policy
Owns permission decisions, filesystem policy, process policy, network policy, credentials/secrets access, destructive operations, installation/update authorization, and audit enforcement.

If Zone D is unavailable, privileged operations fail closed.

### Zone E — External Systems
Includes model providers, GitHub, CAI, Refact, KiCad, MATLAB, LabVIEW, CAD/simulation applications, and future engineering tools.

External systems are untrusted integration boundaries. They never become Ann-E's security authority.

## Dependency direction

Allowed:
```text
Presentation
    ↓
Orchestration
    ↓
Policy Broker
    ↓
Tool / Integration Workers
    ↓
External Systems

Orchestration ──→ Memory
Orchestration ──→ Artifact Store
Orchestration ──→ Model Gateway
Orchestration ──→ Colony Event Publisher
Self-Extension ──→ Policy Broker
Self-Extension ──→ Artifact/Checkpoint Services
```

Disallowed:
```text
Presentation ──X──→ OS command execution
Presentation ──X──→ secrets
Agent/model ──X──→ privileged worker
Agent/model ──X──→ credentials
Colony ──X──→ policy authority
External framework ──X──→ security authority
Worker ──X──→ unscoped filesystem/network access
```

## Configuration boundary
Non-secret configuration may include feature flags, endpoint names, timeouts, UI preferences, model routing configuration, approved workspace paths, and adapter enablement.

Secrets must be supplied through protected secret mechanisms and must not be committed to source control.

Examples:
- API tokens;
- OAuth refresh tokens;
- private keys;
- signing keys;
- passwords;
- credential cookies;
- session secrets.

## Artifact truth
Artifact state is monotonic only when a real validation operation occurred:

```text
GENERATED
   ↓
PARSED
   ↓
VALIDATED
   ↓
SIMULATED
   ↓
EXPERIMENTALLY_VERIFIED
```

A stronger state must never be asserted merely because an artifact was generated.

## Observability
Every meaningful operation should have request ID, task ID, actor/principal, operation, policy decision, start/end timestamps, outcome, artifact references, validation result, and safe diagnostic reference.

Sensitive payloads are redacted before telemetry storage.

## Self-extension
Self-extension remains controlled:

```text
Discover
  ↓
Proposal
  ↓
Dependency/license review
  ↓
Security review
  ↓
Isolated development
  ↓
Build/test/scan
  ↓
User approval according to policy
  ↓
Checkpoint
  ↓
Staged installation
  ↓
Post-install health
  ↓
Commit or rollback
```

Production changes must not silently alter authentication, authorization, permission policy, secret stores, audit integrity, emergency stop, or protected user data.

## Acceptance criteria
Phase 0.3 is complete when:
- architecture boundaries are documented;
- dependency direction is documented;
- configuration and secret boundaries are documented;
- threat model exists;
- audit/observability requirements exist;
- repository architecture smoke tests pass;
- Phase 0.2 contract tests continue to pass;
- no privileged runtime implementation has been introduced prematurely;
- changes are reviewed through a dedicated Phase 0.3 branch/PR.
