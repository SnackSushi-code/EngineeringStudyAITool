# Phase 1C-B â€” Intelligence Orchestrator

## Purpose

Phase 1C-B adds the intelligence orchestration layer between the Phase 1A model service and the existing runtime execution boundary.

The intelligence layer may:

- convert an `IntelligenceRequest` into a Phase 1A `ModelRequest`;
- invoke `ModelService`;
- validate model response correlation;
- decode a structured intelligence response;
- produce either `FINAL_RESPONSE` or `TOOL_PROPOSAL`.

A `TOOL_PROPOSAL` is data, not execution authority.

## Architecture

```text
User
 |
 v
IntelligenceRequest
 |
 v
IntelligenceOrchestrator
 |
 v
ModelService
 |
 v
ModelRouter / Provider
 |
 v
ModelResponse
 |
 v
Structured intelligence response
 |
 +---------------------+
 |                     |
 v                     v
FINAL_RESPONSE     TOOL_PROPOSAL
                       |
                       v
             Existing runtime boundary
             / TaskOrchestrator
```

## Model Response Envelope

The provider response content is expected to be a JSON object:

```json
{
  "contract_version": "1.0",
  "decision_type": "FINAL_RESPONSE",
  "response_text": "..."
}
```

or:

```json
{
  "contract_version": "1.0",
  "decision_type": "TOOL_PROPOSAL",
  "tool_call": {
    "schema_version": "1.0",
    "request_id": "...",
    "task_id": "...",
    "tool": "...",
    "operation": "...",
    "arguments": {},
    "permissions": [],
    "timeout_ms": 1000,
    "retry_mode": "none",
    "idempotency_key": "..."
  }
}
```

The decoder rejects malformed or contradictory envelopes.

## Security Boundary

`IntelligenceOrchestrator` does not call `ToolExecutor`, `ExecutionCoordinator`, or registered tool handlers.

A tool proposal must cross the existing runtime path before execution. Existing policy authorization, runtime lifecycle, enforcement, validation, and audit remain authoritative.

## Finish Reasons

Phase 1C-B accepts only `FinishReason.STOP` for the structured decision envelope. Partial or truncated model output is rejected rather than interpreted as executable intent.

## Scope

Included:

- model invocation;
- response correlation;
- structured response decoding;
- final response decisions;
- tool proposal decisions;
- tool-call contract reconstruction;
- focused tests.

Not included:

- autonomous execution;
- policy changes;
- runtime enforcement changes;
- provider networking;
- memory;
- planning loops;
- self-update;
- Colony behavior.
