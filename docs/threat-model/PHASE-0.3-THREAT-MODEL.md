# Phase 0.3 Threat Model

## Scope
This covers the Ann-E desktop platform, orchestration runtime, tool workers, engineering integrations, Colony, memory, external AI systems, and self-extension.

## Security objectives
1. Prevent unauthorized execution.
2. Prevent privilege escalation.
3. Prevent secret disclosure.
4. Preserve artifact and provenance integrity.
5. Preserve audit integrity.
6. Prevent malformed model output from becoming unrestricted actions.
7. Contain compromised external integrations.
8. Provide reliable rollback and safe-mode behavior.

## Threats and mitigations

### T1 — Malicious or compromised model output
Examples: prompt injection, tool-call manipulation, malicious generated code.

Mitigations: structured tool calls, policy broker, explicit permissions, sandboxed execution, allowlists, approval gates, resource/time limits.

### T2 — Malicious web content
Examples: prompt injection in documentation or hostile repository content.

Mitigations: treat retrieved content as untrusted; isolate research from execution; provenance tracking; never automatically execute retrieved code.

### T3 — Compromised external framework
Examples: compromised CAI/Refact dependency or vulnerable plugin.

Mitigations: pinned revisions, dependency/SBOM scanning, adapter isolation, sandboxing, replaceability, security review.

### T4 — Compromised engineering application
Mitigations: subprocess isolation, explicit workspace scope, artifact validation, timeouts, least privilege.

### T5 — Malicious or accidental self-update
Mitigations: isolated worktree, tests, security scan, checkpoint, approval, staged update, health check, rollback, audit record.

### T6 — Secret leakage
Potential sources: logs, model context, error messages, telemetry, artifacts, environment inheritance.

Mitigations: secret-store isolation, redaction, deny secrets in model-visible state, restricted worker environments, secret scanning.

### T7 — Data corruption or destructive action
Mitigations: destructive permission class, explicit approval, backups/checkpoints, idempotency, transactions where practical, rollback.

## Security invariants
1. No agent can directly grant itself permission.
2. No worker can broaden a permission scope.
3. Policy failure denies privileged actions.
4. Secrets are never serialized into model-visible state.
5. Colony cannot authorize operations.
6. External frameworks cannot become policy authorities.
7. Audit records cannot be rewritten by ordinary application components.
8. Self-update cannot bypass its configured approval policy.

## Residual risk
No architecture eliminates all risk. Every new integration must receive a threat review proportional to its privilege.
