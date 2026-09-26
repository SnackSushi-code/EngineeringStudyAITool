# Phase 0.2 — Ann-E System Contracts

## Purpose

This document defines the first stable contracts between Ann-E's presentation, orchestration, policy, tools, memory, Colony, and self-extension subsystems.

These contracts are implementation boundaries, not UI details. Later code must conform to them or introduce an explicit versioned migration.

## Contract principles

1. Every cross-process request has a unique `request_id` and `task_id`.
2. Every privileged operation declares its permission class before execution.
3. Agents can propose tool calls; the policy broker authorizes or denies them.
4. Tool results must identify artifacts, validation state, provenance, and errors.
5. Unknown fields must be ignored by readers when safe; required fields must be validated.
6. Breaking changes require a contract version increment and migration plan.
7. No secret, credential, raw access token, or unrestricted capability is serialized into model-visible state.
8. Idempotency must be explicit. Retries are permitted only when an operation is idempotent or has a safe retry key.
9. Cancellation is cooperative and must produce a terminal task state.
10. Audit records are append-only from application components.

## 1. Task contract

### TaskRequest

```json
{
  "schema_version": "1.0",
  "request_id": "uuid",
  "task_id": "uuid",
  "created_at": "RFC-3339 timestamp",
  "source": "ui|api|agent|system",
  "user_intent": "string",
  "priority": "low|normal|high|critical",
  "workspace_id": "uuid",
  "requested_capabilities": ["capability.id"],
  "approval_context": {
    "required": true,
    "approval_id": null
  },
  "input_artifacts": ["artifact-id"]
}
```

### TaskState

Allowed terminal states:

- `SUCCEEDED`
- `FAILED`
- `CANCELLED`
- `DENIED`
- `TIMED_OUT`

Non-terminal states:

- `QUEUED`
- `PLANNING`
- `WAITING_APPROVAL`
- `RUNNING`
- `VALIDATING`
- `ROLLING_BACK`

A task must never move from a terminal state back into an active state.

## 2. Tool-call contract

```json
{
  "schema_version": "1.0",
  "request_id": "uuid",
  "task_id": "uuid",
  "tool": "namespace.tool",
  "operation": "operation_name",
  "arguments": {},
  "permissions": [
    {
      "class": "READ|WRITE|EXECUTE|NETWORK|DESTRUCTIVE|SECURITY_SENSITIVE|SELF_UPDATE",
      "scope": "specific approved scope"
    }
  ],
  "timeout_ms": 30000,
  "retry": {
    "mode": "none|safe",
    "idempotency_key": "string"
  }
}
```

The worker must not broaden the requested permission scope.

## 3. Tool-result contract

```json
{
  "schema_version": "1.0",
  "request_id": "uuid",
  "task_id": "uuid",
  "status": "SUCCEEDED|FAILED|CANCELLED|TIMED_OUT",
  "result": {},
  "artifacts": ["artifact-id"],
  "validation": {
    "state": "GENERATED|PARSED|VALIDATED|SIMULATED|EXPERIMENTALLY_VERIFIED|NOT_APPLICABLE",
    "checks": []
  },
  "provenance": {
    "tool": "string",
    "tool_version": "string",
    "adapter_version": "string"
  },
  "error": null,
  "logs": ["log-artifact-id"]
}
```

An artifact may only be promoted to a stronger validation state after the corresponding validation operation actually occurs.

## 4. Permission contract

Permission evaluation is centralized.

```json
{
  "schema_version": "1.0",
  "request_id": "uuid",
  "principal": {
    "type": "agent|user|system|integration",
    "id": "string"
  },
  "action": {
    "class": "READ|WRITE|EXECUTE|NETWORK|DESTRUCTIVE|SECURITY_SENSITIVE|SELF_UPDATE",
    "target": "resource identifier"
  },
  "reason": "human-readable reason",
  "task_id": "uuid"
}
```

Broker response:

```json
{
  "decision": "ALLOW|DENY|REQUIRE_APPROVAL",
  "approval_id": null,
  "policy_version": "string",
  "expires_at": "RFC-3339 timestamp"
}
```

Default failure mode is deny.

## 5. Artifact contract

Every artifact has:

- immutable `artifact_id`
- content hash
- media/type information
- creator task
- workspace/project
- creation timestamp
- provenance
- validation state
- parent artifacts when derived
- retention/deletion policy

Artifacts should be content-addressable where practical.

## 6. Memory contract

Memory is not a raw transcript store.

```json
{
  "schema_version": "1.0",
  "memory_id": "uuid",
  "layer": "SESSION|USER|PROJECT|ENGINEERING|STUDY|RESEARCH|SYSTEM",
  "content": "structured memory",
  "source_refs": ["source-id"],
  "confidence": 0.0,
  "created_at": "RFC-3339 timestamp",
  "last_validated_at": null,
  "status": "PROPOSED|APPROVED|STALE|REVOKED"
}
```

Research-derived memories must retain source references. Conflicting information must remain distinguishable rather than silently overwritten.

## 7. Colony event contract

Colony is a visualization/simulation client, not a security authority.

Events:

```json
{
  "schema_version": "1.0",
  "event_id": "uuid",
  "timestamp": "RFC-3339 timestamp",
  "simulation_tick": 12345,
  "type": "AGENT_CREATED|AGENT_MOVED|TASK_ASSIGNED|TASK_STARTED|TASK_COMPLETED|WARNING|ERROR|STATE_CHANGED",
  "agent_id": "uuid",
  "task_id": "uuid",
  "payload": {}
}
```

Colony receives sanitized operational state. It never receives secrets or unrestricted credentials.

## 8. Self-extension contract

Every proposed capability change records:

- proposal ID
- requested capability
- rationale
- source/repository
- exact revision
- checksum where available
- license
- dependency tree
- security-scan results
- tests
- compatibility results
- risk classification
- approval status
- checkpoint
- rollback target
- post-install health result

Production activation is blocked until the configured approval policy is satisfied.

## 9. Error contract

Errors are structured:

```json
{
  "code": "ANN_E_ERROR_CODE",
  "message": "safe user-facing message",
  "retryable": false,
  "request_id": "uuid",
  "task_id": "uuid",
  "details": {},
  "recovery": "optional recovery instruction"
}
```

Sensitive implementation details belong in protected diagnostics, not model-visible or user-facing error text.

## 10. Versioning

Contract versions use semantic compatibility rules:

- additive optional fields: compatible
- new enum values: requires tolerant readers
- changing field meaning: breaking
- changing required fields: breaking
- removing fields: breaking
- changing permission semantics: security-breaking and requires explicit review

Breaking changes require:

1. new contract version
2. migration adapter
3. compatibility tests
4. rollout/rollback plan
5. architecture decision record when security or trust boundaries change

## Acceptance tests

Phase 0.2 is complete when:

- a TaskRequest can be validated and routed;
- a ToolCall cannot bypass the policy broker;
- denied operations remain denied when the broker fails;
- ToolResults preserve artifact and validation truth;
- Colony can consume sanitized events;
- memory entries preserve provenance;
- self-extension proposals preserve source, revision, test, approval, and rollback metadata;
- contract versions are machine-validatable;
- malformed requests fail closed with structured errors.
