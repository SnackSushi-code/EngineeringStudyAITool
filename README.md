# Ann-E

Ann-E is a desktop-first personal AI engineering companion combining AI assistance, engineering workflows, study tools, persistent learning, a Colony multi-agent environment, voice, and security/auditing.

## Phase 0 â€” Foundation

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

Phase 0 foundation is in the production completion-gate stage.

The current Phase 0 enforcement baseline includes:

- runtime execution contracts;
- authorization and supervisor boundaries;
- Windows Job Object process enforcement;
- explicit unsupported enforcement gaps;
- supervisor-to-platform enforcement integration;
- cleanup and timeout enforcement paths.

Phase 0 is considered complete only after the repository passes the documented completion gate in `docs/architecture/PHASE-0-COMPLETION-GATE.md`.
