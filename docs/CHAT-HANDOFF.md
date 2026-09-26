# Ann-E Chat Handoff

## How to Resume

If this work moves to another ChatGPT conversation, begin with:

> Continue Ann-E development from the repository. Read `docs/PROJECT-STATUS.md`, `docs/DEVELOPMENT-ROADMAP.md`, and `docs/CHAT-HANDOFF.md` before making changes.

Repository:
`SnackSushi-code/EngineeringStudyAITool`

## Current Position

Current branch:
`phase-0.4/runtime-foundation`

Latest commit:
`fdd0705`

Commit:
`feat: add Phase 0.4.1 runtime foundation`

Current milestone:
**Phase 0.4.1 complete**

Next milestone:
**Phase 0.4.2 Runtime Orchestration**

## Immediate Next Work

Prepare and implement Phase 0.4.2 around the existing runtime foundation.

Do not skip ahead to desktop UI, AI providers, Colony, engineering integrations, CAI, Refact, or voice merely because they are more visible.

The next runtime layer should establish:
1. Task orchestration
2. Request/task/tool correlation
3. Lifecycle handling
4. Cancellation
5. Timeout handling
6. Safe retry/idempotency
7. Tool-call validation
8. Tool-result validation
9. Policy integration
10. Audit integration
11. Failure handling
12. Tests for all of the above

## Critical Architecture Rules

- Presentation is never privileged.
- Agents propose actions; policy authorizes them.
- Policy failure fails closed.
- Workers cannot broaden their permission scope.
- Secrets never enter model-visible state.
- Colony cannot authorize operations.
- External frameworks cannot become policy authorities.
- Audit records cannot be rewritten by ordinary application components.
- Self-extension cannot bypass configured approval policy.
- Privileged execution must not be introduced before its security boundary is ready.
- Generated packaging artifacts such as `*.egg-info/` must remain ignored.

## Current Validation Baseline

Phase 0.4.1 was validated with:
- 17/17 runtime tests
- 6/6 architecture tests
- 19/19 contract tests
- 12/12 schemas structurally valid
- date-time, URI, and UUID format checkers registered
- Git whitespace checks clean

## Important Repository History

Major completed commits include:
- Phase 0.1 technology architecture
- Phase 0.2 system contracts
- Phase 0.2.2 comprehensive contract validation
- Phase 0.2.3 CI foundation
- Phase 0.3 architecture hardening
- `fdd0705` Phase 0.4.1 runtime foundation

## Working Style

The user wants company-grade quality:
- prefer correctness over speed
- do not promise zero bugs
- validate before committing
- inspect staged diffs
- keep security boundaries explicit
- avoid premature privileged capabilities
- maintain documentation alongside implementation
- create tests for important failure modes
- preserve rollback/recovery paths

## Chat Continuity

The chat is not the source of truth.

The repository documentation, Git history, contracts, architecture records, and tests are the durable project state.

When starting a new conversation, read these three files first:
- `docs/PROJECT-STATUS.md`
- `docs/DEVELOPMENT-ROADMAP.md`
- `docs/CHAT-HANDOFF.md`
