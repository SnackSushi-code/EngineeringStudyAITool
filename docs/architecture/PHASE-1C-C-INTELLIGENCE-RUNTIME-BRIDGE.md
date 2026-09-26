# Phase 1C-C â€” Intelligence Runtime Bridge

## Purpose

Phase 1C-C provides the explicit boundary that hands a validated intelligence
`TOOL_PROPOSAL` to the existing `TaskOrchestrator`.

The bridge does not execute tools itself.

## Flow

```text
IntelligenceOrchestrator
        |
        v
IntelligenceInvocation
        |
        | TOOL_PROPOSAL only
        v
IntelligenceRuntimeBridge
        |
        | correlated TaskRequest + ToolCall
        v
Existing TaskOrchestrator
        |
        v
ExecutionCoordinator
        |
        v
Policy / AuthorizedToolRunner
        |
        v
ToolExecutor / runtime enforcement
```

## Important design decision

`IntelligenceRequest` does not contain all fields required by the existing
`TaskRequest` contract, such as `workspace_id`, `source`, priority, and artifact
context.

Therefore Phase 1C-C does **not** invent those values.

The caller supplies the authoritative `TaskRequest`. The bridge verifies that
its `request_id` and `task_id` match the intelligence request and that the
proposed `ToolCall` matches the same correlation IDs.

This keeps runtime context construction outside the model/intelligence layer.

## Security properties

The bridge:

- accepts only `TOOL_PROPOSAL`;
- rejects `FINAL_RESPONSE`;
- validates request/task correlation before delegation;
- forwards an existing `CancellationToken`;
- calls only the existing `TaskOrchestrator` boundary;
- never calls `ToolExecutor` directly;
- never calls a tool handler;
- never authorizes permissions itself;
- never changes policy decisions;
- never fabricates workspace, approval, or artifact context.

The existing runtime remains authoritative for schema validation, policy
authorization, lifecycle, execution, timeout behavior, validation, audit, and
enforcement.

## Scope

Included:

- explicit intelligence-to-runtime bridge;
- correlation validation;
- TaskOrchestrator delegation;
- cancellation propagation;
- focused tests;
- architecture documentation.

Not included:

- planning loops;
- autonomous retries at the intelligence layer;
- policy changes;
- model-provider changes;
- memory;
- self-update;
- Colony;
- direct tool execution.
