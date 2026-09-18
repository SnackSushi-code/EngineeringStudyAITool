# Ann-E Threat Model — Phase 0 Baseline

## Assets

- user files and projects
- credentials/API keys
- source code
- engineering designs
- persistent memory/knowledge
- audit history
- Ann-E configuration
- tool execution privileges
- Colony control state

## Primary threats

### T1 — Prompt injection
Untrusted documents/web pages attempt to manipulate agent behavior.

**Controls:** treat retrieved content as untrusted data; separate instructions from source content; policy-check every tool call.

### T2 — Malicious dependency/plugin
A new integration contains harmful code.

**Controls:** provenance, license/dependency review, sandboxing, least privilege, security scans, approval gate, pinned revisions.

### T3 — Destructive tool execution
A model proposes a harmful filesystem/system operation.

**Controls:** capability allowlists, argument validation, approval gates, sandboxing, resource limits, audit trail.

### T4 — Credential exfiltration
A tool or model attempts to expose secrets.

**Controls:** secret isolation, scoped credentials, redaction, no secret injection into prompts unless required, audit events.

### T5 — Compromised self-update
A proposed Ann-E update attempts to bypass controls.

**Controls:** protected update service, signed/versioned artifacts, isolated build/test environment, user approval, rollback, immutable audit trail.

### T6 — Supply-chain compromise
An external repository/release changes unexpectedly.

**Controls:** pin exact revisions, record hashes where applicable, review manifests, SBOM, dependency monitoring.

### T7 — Colony privilege confusion
A simulated Colony worker is treated as if it has direct real-world authority.

**Controls:** Colony workers call the same policy broker as other agents; simulation state is not authority; real-world actions require normal permissions.

### T8 — Faulty engineering output
Generated schematic/code/calculation is accepted without validation.

**Controls:** artifact states (generated/parsed/validated/simulated/experimentally verified), tool-level validation, provenance, explicit limitations.

## Security invariants

1. No agent can grant itself new privileges.
2. No plugin can disable the audit or emergency-stop layer.
3. User data cannot be deleted by an update rollback.
4. Untrusted content cannot directly become executable instructions.
5. Production self-modification is privileged.
