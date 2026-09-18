# Security Boundaries

## Trust zones

### Zone 0 — User / OS
The operating system and user-owned data. Ann-E must treat these as protected.

### Zone 1 — Ann-E Core
Orchestration, configuration and non-privileged logic.

### Zone 2 — Untrusted Model/Agent Output
Model output is data, not authority. Prompt-injected or malformed output is expected to occur.

### Zone 3 — Tool Broker
Validates capability, arguments, policy, identity, approval requirements and resource limits.

### Zone 4 — Sandboxed Workers
Perform code execution, external software automation and other risky actions with minimal privileges.

### Zone 5 — Audit / Recovery
Protected event log, checkpoints and rollback controls. Ordinary agents cannot disable or rewrite this layer.

## Protected capabilities

The following require explicit policy controls and normally user approval:
- destructive filesystem operations
- system configuration
- credential access
- installing arbitrary software
- production infrastructure changes
- external communications
- security testing outside explicitly authorized targets

## Self-extension rule

Ann-E may research, design, implement and test a proposed extension in an isolated development environment. Production activation is a separate privileged operation.
