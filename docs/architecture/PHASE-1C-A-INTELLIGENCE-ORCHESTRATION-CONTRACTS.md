# Phase 1C-A — Intelligence Orchestration Contracts

Phase 1C-A establishes the contract boundary between Ann-E intelligence, the Phase 1A model layer, and the existing runtime/tool execution system.

## Architecture Boundary

User Request -> IntelligenceRequest -> Phase 1A ModelRequest -> Model Provider -> IntelligenceDecision -> FINAL_RESPONSE or TOOL_PROPOSAL -> Existing Runtime Tool/Task Boundary.

## Correlation

Runtime request_id and task_id remain UUID values. The Phase 1A model boundary uses string identifiers. IntelligenceRequest provides the explicit conversion through model_request_id, model_task_id, and to_model_request(). IntelligenceResult validates model and tool correlation.

## Decision Types

FINAL_RESPONSE contains response text and no tool call. TOOL_PROPOSAL contains a ToolCall and no response text. A tool proposal is not execution authority.

## Security Boundary

The intelligence layer does not authorize or directly execute tools. Tool proposals cross into the existing runtime/tool capability boundary, where policy, authorization, orchestration, enforcement, validation, and audit remain authoritative.

## Existing Runtime Orchestrator

The existing anne_runtime.orchestrator.TaskOrchestrator is retained and is not replaced or renamed by Phase 1C-A. Its responsibility remains runtime task lifecycle and execution management.

## Phase 1C-A Scope

Included: intelligence request contract, Phase 1A model bridge, intelligence decision contract, correlation validation, tool proposal validation, serialization, and focused tests.

Not included: model provider implementation, autonomous tool execution, authorization changes, runtime enforcement changes, self-update behavior, agent memory, planning loops, or Colony behavior.
