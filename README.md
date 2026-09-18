# Ann-E

Ann-E is a desktop-first personal AI engineering companion combining AI assistance, engineering workflows, study tools, persistent learning, a Colony multi-agent environment, voice, and security/auditing.

## Phase 0 — Foundation

Phase 0 deliberately establishes architecture and safety boundaries before feature implementation.

### Non-negotiable engineering principles
- No direct unrestricted model-to-OS access.
- All tool execution passes through authorization, sandboxing, validation, and auditing.
- Production self-updates require user authorization by default.
- Generated engineering artifacts are never represented as validated unless validation actually ran.
- External repositories are integrated through pinned, reviewed adapters where practical.
- Every major capability has automated tests and a documented failure path.

## Repository

See:
- `docs/architecture/system-overview.md`
- `docs/architecture/repository-structure.md`
- `docs/architecture/security-boundaries.md`
- `docs/adr/`
- `docs/threat-model/threat-model.md`
- `docs/quality-gates.md`

## Phase 0 status

- [x] Architecture baseline
- [x] Security boundary baseline
- [x] Threat model baseline
- [x] Repository scaffold
- [x] ADR baseline
- [x] Quality gates
- [ ] Desktop runtime
- [ ] AI provider implementation
- [ ] Tool broker implementation

Feature implementation begins only after the Phase 0 review is accepted.
