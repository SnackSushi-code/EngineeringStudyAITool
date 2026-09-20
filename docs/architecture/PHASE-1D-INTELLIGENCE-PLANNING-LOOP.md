# Phase 1D â€” Intelligence Planning Loop

## Purpose

Phase 1D adds a bounded planning loop that sequences intelligence decisions and
runtime outcomes.

The loop does not become a second execution or authorization system.

## Flow

```text
User Intent
    |
    v
IntelligencePlanningLoop
    |
    v
IntelligenceOrchestrator
    |
    +--------------------+
    |                    |
    v                    v
FINAL_RESPONSE      TOOL_PROPOSAL
    |                    |
    |                    v
    |          IntelligenceRuntimeBridge
    |                    |
    |                    v
    |             TaskOrchestrator
    |                    |
    |                    v
    |               Tool Result
    |                    |
    +<-------------------+
             |
             v
      Next bounded iteration
```

## Responsibilities

The planning loop owns:

- bounded iteration count;
- sequencing model decisions and runtime outcomes;
- feeding successful tool outcomes back into the next intelligence request;
- cancellation observation between iterations;
- terminal reporting when a final response is produced;
- explicit stop reasons when a tool fails, is denied, is cancelled, times out,
  or the iteration budget is exhausted.

## Non-responsibilities

The planning loop does not:

- authorize permissions;
- execute tools directly;
- call `ToolExecutor`;
- bypass `TaskOrchestrator`;
- fabricate `TaskRequest` context;
- change policy decisions;
- automatically retry non-successful runtime outcomes;
- expose runtime logs as model conversation content.

## Conversation propagation

`IntelligenceRequest.conversation` is now converted into the existing
`ModelMessage` contract.

Each planning iteration retains the original user intent and adds:

1. an assistant message describing the tool proposal;
2. a tool message containing a bounded projection of the runtime outcome.

Internal runtime logs are intentionally excluded from the tool message.

## Termination

The loop stops when:

- the intelligence layer produces `FINAL_RESPONSE`;
- cancellation is requested;
- a tool outcome is not `SUCCEEDED`;
- the maximum iteration count is reached.

A planning loop that reaches its iteration limit does not fabricate a final answer.

## Security boundary

The planning loop is sequencing logic only.

Authorization remains in the existing runtime policy/execution path.
Execution remains behind `IntelligenceRuntimeBridge` and `TaskOrchestrator`.
Runtime enforcement, validation, lifecycle, and audit remain authoritative.
