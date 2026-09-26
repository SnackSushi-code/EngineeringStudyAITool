# Phase 1B — Tool & Capability System

Phase 1A established the model-provider boundary. Phase 1B establishes the controlled boundary between model reasoning and executable operations.

## Security invariant

A registered handler is never invoked until:

1. The tool exists in the explicit registry.
2. The invocation matches the registered descriptor.
3. Arguments pass the declared schema.
4. Every descriptor-declared permission is present in the ToolCall.
5. Every required permission is evaluated by the PolicyBroker.
6. Every required permission returns `ALLOW`.

`DENY` and `REQUIRE_APPROVAL` are fail-closed and never execute the handler.

## Components

- `tool_contracts.py`: typed descriptors, argument schemas, invocation validation, execution context, result validators, audit events.
- `tool_registry.py`: explicit deterministic mapping of tool IDs to descriptors and handlers.
- `tool_executor.py`: authorization gate, bounded execution, timeout/cancellation signal, safe retry, result validation, provenance, and audit events.
- `tool_test_tools.py`: deterministic handlers used only by automated tests.

## Retry semantics

Retry is opt-in on both the descriptor and request and is limited to one retry. This phase does not infer safety from arbitrary tool behavior.

## Timeout semantics

Execution uses a worker thread and returns a timeout result without waiting for the full handler duration. Cooperative handlers can observe the cancellation event. Thread interruption is not claimed as an OS-level kill mechanism; stronger process isolation belongs to the existing runtime enforcement architecture.

## Authorization boundary

`PolicyBroker` remains an authorization component. It does not execute tools. `ToolExecutor` is the enforcement point that prevents a denied operation from reaching the handler.

## Validation

Tool results may have an optional validator. A failed validator produces a terminal failed `ToolResult` and an audit event.

## Scope deliberately excluded

This phase does not grant tools direct OS privileges, credentials, network access, or unrestricted filesystem access. Real privileged tools must be integrated later through the existing authorization and runtime-enforcement architecture.
