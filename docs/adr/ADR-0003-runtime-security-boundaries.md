# ADR-0003: Ann-E Runtime and Security Boundaries

- Status: Accepted for Phase 0.1
- Date: 2026-09-18

## Decision

Ann-E will be divided into trust zones.

### Zone A — Presentation

Contains:
- React UI
- Ann-E widget
- user interaction
- visual telemetry
- Colony client/visualization

May:
- request operations through typed APIs
- display sanitized results

May not:
- execute arbitrary OS commands
- read secrets
- write outside approved application/project locations
- directly call engineering software

### Zone B — Orchestration

Contains:
- task planning
- agent routing
- model gateway
- workflow state
- approvals
- memory retrieval
- tool scheduling

May:
- request tools through the policy broker
- access approved memory
- create task plans

May not:
- bypass policy enforcement
- silently elevate permissions

### Zone C — Tool/Integration Workers

Contains:
- KiCad
- MATLAB
- LabVIEW
- CAD/simulation adapters
- Git/GitHub operations
- code execution

Each worker receives:
- explicit task ID
- minimum required permissions
- input artifact references
- time/resource limits

Each worker returns:
- structured result
- logs
- output artifact references
- validation status
- provenance

### Zone D — Security/Policy Broker

The broker is the authority for:
- filesystem access
- process execution
- network access
- credentials
- secrets
- destructive actions
- installation/update actions

No model or agent may directly bypass the broker.

## Approval classes

1. READ — automatically allowed inside approved scopes.
2. WRITE — allowed only inside approved project/workspace scopes.
3. EXECUTE — sandboxed and policy checked.
4. NETWORK — domain/purpose constrained.
5. DESTRUCTIVE — explicit user approval.
6. SECURITY-SENSITIVE — explicit user approval plus security policy.
7. SELF-UPDATE — explicit user approval by default.

## CAI and Refact

CAI and Refact are integration candidates, not trust anchors.

Current public repositories are archived. CAI is explicitly described by its maintainers as unmaintained and warns about using it in isolated environments; its GitHub security page lists critical command-injection advisories. Refact's original repository is also archived and directs new development to a successor location. Therefore Ann-E must isolate both behind adapters and must not make them production-critical dependencies. citeturn0search0turn0search10turn0search1turn0search4

## Rule

An external agent framework may propose or perform an operation only through Ann-E's policy-controlled tool interface.

The framework never becomes the policy authority.

## Failure behavior

If the policy broker is unavailable:
- deny privileged operations
- preserve read-only UI where possible
- show a clear degraded state
- log the denial
- never fall back to unrestricted execution
