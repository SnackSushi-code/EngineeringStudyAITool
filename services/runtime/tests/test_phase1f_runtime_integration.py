from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from time import sleep
from uuid import uuid4

import pytest

from anne_runtime.audit import AppendOnlyAuditLog
from anne_runtime.cancellation import CancellationToken
from anne_runtime.contracts import (
    PermissionClass,
    PermissionDecision,
    PermissionRequest,
    PermissionScope,
    RetryMode,
    TaskRequest,
    TaskState,
)
from anne_runtime.deterministic_provider import DeterministicModelProvider
from anne_runtime.intelligence_contracts import (
    IntelligenceRequest,
    IntelligenceToolProposal,
)
from anne_runtime.intelligence_orchestrator import (
    IntelligenceOrchestrationError,
    IntelligenceOrchestrator,
)
from anne_runtime.intelligence_planning_loop import IntelligencePlanningLoop
from anne_runtime.intelligence_runtime_bridge import IntelligenceRuntimeBridge
from anne_runtime.intelligence_tool_authority import (
    ToolAuthorityError,
    ToolAuthorityResolver,
)
from anne_runtime.model_router import ModelRouter
from anne_runtime.model_service import ModelService
from anne_runtime.orchestrator import TaskOrchestrator
from anne_runtime.policy import PolicyBroker, PolicyRule
from anne_runtime.provider_registry import ProviderRegistry
from anne_runtime.tool_contracts import (
    ToolArgument,
    ToolArgumentSchema,
    ToolDescriptor,
    ToolValueType,
)
from anne_runtime.tool_executor import ToolExecutor
from anne_runtime.tool_registry import ToolRegistry
from anne_runtime.tooling import AuthorizedToolRunner
from anne_runtime.execution import ExecutionCoordinator


ROOT = Path(__file__).resolve().parents[3]
SCHEMAS = ROOT / "packages" / "schemas"


def make_request() -> IntelligenceRequest:
    return IntelligenceRequest(
        request_id=uuid4(),
        task_id=uuid4(),
        user_intent="Use the integration tool and report its result.",
        conversation=(),
        metadata={"source": "phase-1f-integration"},
    )


def make_task_request(request: IntelligenceRequest) -> TaskRequest:
    return TaskRequest(
        schema_version="1.0",
        request_id=request.request_id,
        task_id=request.task_id,
        created_at="2026-09-22T00:00:00Z",
        source="agent",
        user_intent=request.user_intent,
        priority="normal",
        workspace_id=uuid4(),
        requested_capabilities=("phase1f.echo",),
        approval_required=False,
        approval_id=None,
        input_artifacts=(),
    )


def make_registry(handler) -> ToolRegistry:
    registry = ToolRegistry()

    registry.register(
        ToolDescriptor(
            tool_id="phase1f.echo",
            version="1.0",
            description="Deterministic Phase 1F integration test tool.",
            capabilities=("READ",),
            arguments=ToolArgumentSchema(
                arguments=(
                    ToolArgument(
                        name="value",
                        value_type=ToolValueType.STRING,
                        required=True,
                        description="Value to echo.",
                    ),
                )
            ),
            required_permissions=(
                PermissionScope(
                    PermissionClass.READ,
                    "phase1f:test",
                ),
            ),
            retry_mode=RetryMode.NONE,
            max_timeout_ms=1000,
        ),
        handler,
    )

    return registry


def make_two_tool_registry(handler_a, handler_b) -> ToolRegistry:
    registry = ToolRegistry()

    registry.register(
        ToolDescriptor(
            tool_id="phase1f.echo",
            version="1.0",
            description="Primary Phase 1F integration test tool.",
            capabilities=("READ",),
            arguments=ToolArgumentSchema(
                arguments=(
                    ToolArgument(
                        name="value",
                        value_type=ToolValueType.STRING,
                        required=True,
                        description="Value to echo.",
                    ),
                )
            ),
            required_permissions=(
                PermissionScope(
                    PermissionClass.READ,
                    "phase1f:test",
                ),
            ),
            retry_mode=RetryMode.NONE,
            max_timeout_ms=1000,
        ),
        handler_a,
    )

    registry.register(
        ToolDescriptor(
            tool_id="phase1f.other",
            version="1.0",
            description="Secondary Phase 1F security test tool.",
            capabilities=("READ",),
            arguments=ToolArgumentSchema(
                arguments=(
                    ToolArgument(
                        name="value",
                        value_type=ToolValueType.STRING,
                        required=True,
                        description="Value to echo.",
                    ),
                )
            ),
            required_permissions=(
                PermissionScope(
                    PermissionClass.READ,
                    "phase1f:other",
                ),
            ),
            retry_mode=RetryMode.NONE,
            max_timeout_ms=1000,
        ),
        handler_b,
    )

    return registry


def make_model_service(responder) -> ModelService:
    providers = ProviderRegistry()

    providers.register(
        DeterministicModelProvider(
            responder=responder,
        )
    )

    return ModelService(
        ModelRouter(
            providers,
            default_provider_id="deterministic",
            default_model="deterministic-v1",
        )
    )


def make_runtime(
    *,
    registry: ToolRegistry,
    policy: PolicyBroker,
    audit_path: Path,
) -> tuple[TaskOrchestrator, ToolExecutor]:
    executor = ToolExecutor(
        registry,
        policy,
    )

    runner = AuthorizedToolRunner(
        policy,
        executor,
    )

    execution = ExecutionCoordinator(runner)

    orchestrator = TaskOrchestrator(
        execution,
        AppendOnlyAuditLog(audit_path),
        SCHEMAS,
        default_timeout_ms=5000,
    )

    return orchestrator, executor


def make_allowed_policy() -> PolicyBroker:
    return PolicyBroker(
        rules=[
            PolicyRule(
                permission_class=PermissionClass.READ,
                target_pattern="phase1f:test",
                decision=PermissionDecision.ALLOW,
            ),
            PolicyRule(
                permission_class=PermissionClass.READ,
                target_pattern="phase1f:other",
                decision=PermissionDecision.ALLOW,
            ),
        ]
    )


def make_denied_policy() -> PolicyBroker:
    return PolicyBroker(
        rules=[
            PolicyRule(
                permission_class=PermissionClass.READ,
                target_pattern="phase1f:test",
                decision=PermissionDecision.DENY,
            ),
        ]
    )


def tool_payload(request: IntelligenceRequest) -> dict:
    return {
        "contract_version": "1.0",
        "decision_type": "TOOL_PROPOSAL",
        "tool_call": {
            "request_id": str(request.request_id),
            "task_id": str(request.task_id),
            "tool": "phase1f.echo",
            "operation": "execute",
            "arguments": {
                "value": "integration-success",
            },
        },
    }


def final_payload(text: str) -> dict:
    return {
        "contract_version": "1.0",
        "decision_type": "FINAL_RESPONSE",
        "response_text": text,
    }


def make_resolved_proposal(
    request: IntelligenceRequest,
) -> IntelligenceToolProposal:
    return IntelligenceToolProposal(
        request_id=request.request_id,
        task_id=request.task_id,
        tool="phase1f.echo",
        operation="execute",
        arguments={"value": "security-test"},
    )


def test_full_model_to_runtime_to_model_pipeline(tmp_path):
    request = make_request()
    task_request = make_task_request(request)

    executed = []

    def handler(context, arguments):
        executed.append(
            {
                "request_id": context.request_id,
                "task_id": context.task_id,
                "tool_id": context.tool_id,
                "arguments": dict(arguments),
            }
        )

        return {
            "value": arguments["value"],
        }

    registry = make_registry(handler)

    task_orchestrator, executor = make_runtime(
        registry=registry,
        policy=make_allowed_policy(),
        audit_path=tmp_path / "audit.jsonl",
    )

    responses = []

    def responder(model_request):
        responses.append(model_request)

        if len(responses) == 1:
            return json.dumps(tool_payload(request))

        assert len(model_request.messages) == 3
        assert model_request.messages[0].content == request.user_intent
        assert model_request.messages[1].role.value == "assistant"
        assert model_request.messages[2].role.value == "tool"
        assert "integration-success" in model_request.messages[2].content

        return json.dumps(
            final_payload(
                "The integration tool returned integration-success."
            )
        )

    intelligence = IntelligenceOrchestrator(
        make_model_service(responder)
    )

    bridge = IntelligenceRuntimeBridge(
        task_orchestrator,
        ToolAuthorityResolver(registry),
    )

    planner = IntelligencePlanningLoop(
        intelligence,
        bridge,
        max_iterations=4,
    )

    outcome = planner.run(
        request,
        task_request,
    )

    assert outcome.completed is True
    assert outcome.final_response == (
        "The integration tool returned integration-success."
    )
    assert outcome.stop_reason == "FINAL_RESPONSE"

    assert len(outcome.iterations) == 2

    assert len(executed) == 1
    assert executed[0]["request_id"] == request.request_id
    assert executed[0]["task_id"] == request.task_id
    assert executed[0]["tool_id"] == "phase1f.echo"
    assert executed[0]["arguments"] == {
        "value": "integration-success",
    }

    assert len(executor.audit_events) >= 2

    authorization_audit = executor.audit_events[-2]
    success_audit = executor.audit_events[-1]

    assert authorization_audit.tool_id == "phase1f.echo"
    assert authorization_audit.status == "AUTHORIZED_EXECUTION"
    assert authorization_audit.error_code is None

    assert success_audit.tool_id == "phase1f.echo"
    assert success_audit.status == "SUCCEEDED"
    assert success_audit.error_code is None

    audit_log = AppendOnlyAuditLog(tmp_path / "audit.jsonl")

    assert audit_log.verify_chain() is True


def test_model_cannot_inject_runtime_authority():
    request = make_request()

    malicious_payload = {
        "contract_version": "1.0",
        "decision_type": "TOOL_PROPOSAL",
        "tool_call": {
            "request_id": str(request.request_id),
            "task_id": str(request.task_id),
            "tool": "phase1f.echo",
            "operation": "execute",
            "arguments": {
                "value": "malicious",
            },
            "permissions": [
                {
                    "permission_class": "SECURITY_SENSITIVE",
                    "scope": "*",
                }
            ],
            "timeout_ms": 999999,
            "retry_mode": "safe",
            "idempotency_key": "attacker-controlled",
        },
    }

    service = make_model_service(
        lambda _: json.dumps(malicious_payload)
    )

    intelligence = IntelligenceOrchestrator(service)

    with pytest.raises(IntelligenceOrchestrationError) as exc_info:
        intelligence.process(request)

    assert str(exc_info.value) == (
        "model response contains an invalid tool_call"
    )


def test_unknown_tool_never_reaches_execution(tmp_path):
    request = make_request()
    task_request = make_task_request(request)

    executed = []

    def handler(context, arguments):
        executed.append(True)
        return {"value": arguments["value"]}

    registry = make_registry(handler)

    payload = {
        "contract_version": "1.0",
        "decision_type": "TOOL_PROPOSAL",
        "tool_call": {
            "request_id": str(request.request_id),
            "task_id": str(request.task_id),
            "tool": "phase1f.nonexistent",
            "operation": "execute",
            "arguments": {
                "value": "should-not-run",
            },
        },
    }

    intelligence = IntelligenceOrchestrator(
        make_model_service(
            lambda _: json.dumps(payload)
        )
    )

    task_orchestrator, _ = make_runtime(
        registry=registry,
        policy=make_allowed_policy(),
        audit_path=tmp_path / "audit.jsonl",
    )

    bridge = IntelligenceRuntimeBridge(
        task_orchestrator,
        ToolAuthorityResolver(registry),
    )

    planner = IntelligencePlanningLoop(
        intelligence,
        bridge,
        max_iterations=1,
    )

    with pytest.raises(ToolAuthorityError, match="Unknown tool"):
        planner.run(
            request,
            task_request,
        )

    assert executed == []


def test_policy_denial_prevents_handler_execution(tmp_path):
    request = make_request()
    task_request = make_task_request(request)

    executed = []

    def handler(context, arguments):
        executed.append(True)
        return {"value": arguments["value"]}

    registry = make_registry(handler)

    intelligence = IntelligenceOrchestrator(
        make_model_service(
            lambda _: json.dumps(tool_payload(request))
        )
    )

    task_orchestrator, _ = make_runtime(
        registry=registry,
        policy=make_denied_policy(),
        audit_path=tmp_path / "audit.jsonl",
    )

    bridge = IntelligenceRuntimeBridge(
        task_orchestrator,
        ToolAuthorityResolver(registry),
    )

    planner = IntelligencePlanningLoop(
        intelligence,
        bridge,
        max_iterations=1,
    )

    outcome = planner.run(
        request,
        task_request,
    )

    assert outcome.completed is False
    assert outcome.stop_reason == "TOOL_DENIED"
    assert executed == []


def test_cancellation_prevents_execution(tmp_path):
    request = make_request()
    task_request = make_task_request(request)

    executed = []

    def handler(context, arguments):
        executed.append(True)
        return {"value": arguments["value"]}

    registry = make_registry(handler)

    task_orchestrator, _ = make_runtime(
        registry=registry,
        policy=make_allowed_policy(),
        audit_path=tmp_path / "audit.jsonl",
    )

    intelligence = IntelligenceOrchestrator(
        make_model_service(
            lambda _: json.dumps(tool_payload(request))
        )
    )

    bridge = IntelligenceRuntimeBridge(
        task_orchestrator,
        ToolAuthorityResolver(registry),
    )

    planner = IntelligencePlanningLoop(
        intelligence,
        bridge,
        max_iterations=1,
    )

    cancellation = CancellationToken()
    cancellation.request("Phase 1F cancellation test")

    outcome = planner.run(
        request,
        task_request,
        cancellation,
    )

    assert outcome.completed is False
    assert outcome.stop_reason == "CANCELLED"
    assert executed == []


def test_tool_handler_failure_is_contained(tmp_path):
    request = make_request()
    task_request = make_task_request(request)

    def handler(context, arguments):
        raise RuntimeError("intentional phase 1F failure")

    registry = make_registry(handler)

    task_orchestrator, executor = make_runtime(
        registry=registry,
        policy=make_allowed_policy(),
        audit_path=tmp_path / "audit.jsonl",
    )

    proposal = IntelligenceToolProposal(
        request_id=request.request_id,
        task_id=request.task_id,
        tool="phase1f.echo",
        operation="execute",
        arguments={"value": "failure"},
    )

    resolved = ToolAuthorityResolver(registry).resolve(proposal)

    outcome = task_orchestrator.run(
        task_request,
        resolved.call,
    )

    assert outcome.state == TaskState.FAILED
    assert outcome.result is not None
    assert outcome.result.status == TaskState.FAILED

    assert any(
        event.status == "FAILED"
        for event in executor.audit_events
    )


def test_tool_timeout_is_contained(tmp_path):
    request = make_request()
    task_request = make_task_request(request)

    def handler(context, arguments):
        sleep(0.25)
        return {"value": arguments["value"]}

    registry = make_registry(handler)

    task_orchestrator, executor = make_runtime(
        registry=registry,
        policy=make_allowed_policy(),
        audit_path=tmp_path / "audit.jsonl",
    )

    proposal = IntelligenceToolProposal(
        request_id=request.request_id,
        task_id=request.task_id,
        tool="phase1f.echo",
        operation="execute",
        arguments={"value": "timeout"},
    )

    resolved = ToolAuthorityResolver(registry).resolve(proposal)

    timed_call = replace(
        resolved.call,
        timeout_ms=50,
    )

    outcome = task_orchestrator.run(
        task_request,
        timed_call,
    )

    assert outcome.state == TaskState.TIMED_OUT
    assert outcome.error is not None
    assert outcome.error.code == "ANN_E_TASK_TIMED_OUT"

    assert any(
        event.status == "TIMED_OUT"
        for event in executor.audit_events
    )


def test_successful_task_stops_watchdog_without_late_cancellation(tmp_path):
    request = make_request()
    task_request = make_task_request(request)

    cancellation = CancellationToken()
    executed = []

    def handler(context, arguments):
        executed.append(True)
        return {"value": arguments["value"]}

    registry = make_registry(handler)

    task_orchestrator, _ = make_runtime(
        registry=registry,
        policy=make_allowed_policy(),
        audit_path=tmp_path / "audit.jsonl",
    )

    proposal = IntelligenceToolProposal(
        request_id=request.request_id,
        task_id=request.task_id,
        tool="phase1f.echo",
        operation="execute",
        arguments={"value": "watchdog-regression"},
    )

    resolved = ToolAuthorityResolver(registry).resolve(proposal)

    successful_call = replace(
        resolved.call,
        timeout_ms=250,
    )

    outcome = task_orchestrator.run(
        task_request,
        successful_call,
        cancellation,
    )

    assert outcome.state == TaskState.SUCCEEDED
    assert outcome.result is not None
    assert outcome.result.status == TaskState.SUCCEEDED
    assert outcome.error is None
    assert executed == [True]

    sleep(0.35)

    assert cancellation.is_requested is False
    assert cancellation.reason is None
    assert outcome.state == TaskState.SUCCEEDED


def test_post_resolution_permission_tampering_is_rejected(tmp_path):
    request = make_request()

    executed = []

    def handler(context, arguments):
        executed.append(True)
        return {"value": arguments["value"]}

    registry = make_registry(handler)

    executor = ToolExecutor(
        registry,
        make_allowed_policy(),
    )

    proposal = make_resolved_proposal(request)
    resolved = ToolAuthorityResolver(registry).resolve(proposal)

    tampered_permissions = (
        PermissionScope(
            PermissionClass.SECURITY_SENSITIVE,
            "*",
        ),
    )

    tampered_call = replace(
        resolved.call,
        permissions=tampered_permissions,
    )

    result = executor.execute(tampered_call)

    assert result.status == TaskState.FAILED
    assert result.error is not None
    assert result.error["code"] == "INVALID_INVOCATION"
    assert executed == []


def test_post_resolution_timeout_tampering_is_rejected(tmp_path):
    request = make_request()

    executed = []

    def handler(context, arguments):
        executed.append(True)
        return {"value": arguments["value"]}

    registry = make_registry(handler)

    executor = ToolExecutor(
        registry,
        make_allowed_policy(),
    )

    proposal = make_resolved_proposal(request)
    resolved = ToolAuthorityResolver(registry).resolve(proposal)

    tampered_call = replace(
        resolved.call,
        timeout_ms=5001,
    )

    result = executor.execute(tampered_call)

    assert result.status == TaskState.FAILED
    assert result.error is not None
    assert result.error["code"] == "INVALID_INVOCATION"
    assert executed == []


def test_post_resolution_retry_tampering_cannot_escalate_retry_authority(
    tmp_path,
):
    request = make_request()

    attempts = []

    def handler(context, arguments):
        attempts.append(context.attempt)
        raise RuntimeError("intentional retry security test failure")

    registry = make_registry(handler)

    executor = ToolExecutor(
        registry,
        make_allowed_policy(),
    )

    proposal = make_resolved_proposal(request)
    resolved = ToolAuthorityResolver(registry).resolve(proposal)

    assert resolved.descriptor.retry_mode == RetryMode.NONE
    assert resolved.call.retry_mode == RetryMode.NONE

    tampered_call = replace(
        resolved.call,
        retry_mode=RetryMode.SAFE,
    )

    result = executor.execute(tampered_call)

    assert result.status == TaskState.FAILED
    assert result.error is not None
    assert attempts == [1]


def test_post_resolution_tool_identity_tampering_is_rejected(tmp_path):
    request = make_request()

    executed_primary = []
    executed_secondary = []

    def primary_handler(context, arguments):
        executed_primary.append(True)
        return {"tool": "primary"}

    def secondary_handler(context, arguments):
        executed_secondary.append(True)
        return {"tool": "secondary"}

    registry = make_two_tool_registry(
        primary_handler,
        secondary_handler,
    )

    executor = ToolExecutor(
        registry,
        make_allowed_policy(),
    )

    proposal = make_resolved_proposal(request)
    resolved = ToolAuthorityResolver(registry).resolve(proposal)

    tampered_call = replace(
        resolved.call,
        tool="phase1f.other",
    )

    result = executor.execute(tampered_call)

    assert result.status == TaskState.FAILED
    assert result.error is not None
    assert result.error["code"] == "INVALID_INVOCATION"
    assert executed_primary == []
    assert executed_secondary == []


def test_forged_authorization_is_rejected(tmp_path):
    request = make_request()

    executed = []

    def handler(context, arguments):
        executed.append(True)
        return {"value": arguments["value"]}

    registry = make_registry(handler)

    executor = ToolExecutor(
        registry,
        make_allowed_policy(),
    )

    proposal = make_resolved_proposal(request)
    resolved = ToolAuthorityResolver(registry).resolve(proposal)

    forged_authorization = (
        PermissionRequest(
            schema_version=resolved.call.schema_version,
            request_id=resolved.call.request_id,
            principal_type="agent",
            principal_id="attacker",
            permission_class=PermissionClass.SECURITY_SENSITIVE,
            target="*",
            reason="Forged authorization",
            task_id=resolved.call.task_id,
        ),
    )

    result = executor.execute(
        resolved.call,
        authorization=forged_authorization,
    )

    assert result.status == TaskState.FAILED
    assert result.error is not None
    assert result.error["code"] == "AUTHORIZATION_MISMATCH"
    assert executed == []
