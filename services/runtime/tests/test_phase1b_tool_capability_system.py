from __future__ import annotations

from uuid import uuid4

from anne_runtime.contracts import (
    PermissionClass,
    PermissionDecision,
    PermissionScope,
    RetryMode,
    TaskState,
    ToolCall,
)
from anne_runtime.policy import PolicyBroker, PolicyRule
from anne_runtime.tool_contracts import (
    ToolArgument,
    ToolArgumentSchema,
    ToolContractError,
    ToolDescriptor,
    ToolValueType,
)
from anne_runtime.tool_executor import ToolExecutor
from anne_runtime.tool_registry import ToolRegistry
from anne_runtime.tool_test_tools import (
    CountingTool,
    FailingOnceTool,
    SlowCooperativeTool,
    counting_descriptor,
    retry_descriptor,
    slow_descriptor,
)


def make_call(
    tool: str,
    *,
    arguments=None,
    permissions=(
        PermissionScope(PermissionClass.READ, "test:value"),
    ),
    timeout_ms: int = 1_000,
    retry_mode: RetryMode = RetryMode.NONE,
) -> ToolCall:
    return ToolCall(
        schema_version="1.0",
        request_id=uuid4(),
        task_id=uuid4(),
        tool=tool,
        operation="execute",
        arguments=arguments if arguments is not None else {"value": "hello"},
        permissions=permissions,
        timeout_ms=timeout_ms,
        retry_mode=retry_mode,
        idempotency_key=str(uuid4()),
    )


def allow_policy() -> PolicyBroker:
    return PolicyBroker(
        rules=[
            PolicyRule(
                permission_class=PermissionClass.READ,
                target_pattern="test:*",
                decision=PermissionDecision.ALLOW,
            )
        ],
        policy_version="test-policy-1",
    )


def test_duplicate_registry_registration_is_rejected():
    registry = ToolRegistry()
    descriptor = counting_descriptor()
    registry.register(descriptor, CountingTool())
    try:
        registry.register(descriptor, CountingTool())
    except ToolContractError:
        return
    raise AssertionError("Duplicate registration was accepted.")


def test_replacement_requires_explicit_flag():
    registry = ToolRegistry()
    descriptor = counting_descriptor()
    first = CountingTool()
    second = CountingTool()
    registry.register(descriptor, first)
    try:
        registry.register(descriptor, second)
    except ToolContractError:
        pass
    else:
        raise AssertionError("Implicit replacement was accepted.")
    registry.register(descriptor, second, replace=True)
    assert registry.get("test.counter")[1] is second


def test_argument_schema_rejects_unknown_argument():
    schema = ToolArgumentSchema((
        ToolArgument("value", ToolValueType.STRING, required=True),
    ))
    try:
        schema.validate({"value": "ok", "unexpected": True})
    except ToolContractError:
        return
    raise AssertionError("Unknown argument was accepted.")


def test_argument_schema_rejects_wrong_type():
    schema = ToolArgumentSchema((
        ToolArgument("value", ToolValueType.STRING, required=True),
    ))
    try:
        schema.validate({"value": 123})
    except ToolContractError:
        return
    raise AssertionError("Wrong argument type was accepted.")


def test_denied_tool_never_executes():
    registry = ToolRegistry()
    handler = CountingTool()
    registry.register(counting_descriptor(), handler)
    result = ToolExecutor(registry, PolicyBroker()).execute(make_call("test.counter"))
    assert result.status == TaskState.DENIED
    assert handler.count == 0


def test_approval_required_never_executes_and_surfaces_control_flow():
    registry = ToolRegistry()
    handler = CountingTool()
    registry.register(counting_descriptor(), handler)

    policy = PolicyBroker(rules=[
        PolicyRule(
            permission_class=PermissionClass.READ,
            target_pattern="test:*",
            decision=PermissionDecision.REQUIRE_APPROVAL,
        )
    ])

    executor = ToolExecutor(registry, policy)

    from anne_runtime.tool_contracts import ToolApprovalRequiredError

    try:
        executor.execute(make_call("test.counter"))
    except ToolApprovalRequiredError as exc:
        assert exc.permission_class == PermissionClass.READ.value
        assert exc.target == "test:value"
        assert exc.decision.decision == PermissionDecision.REQUIRE_APPROVAL
    else:
        raise AssertionError(
            "Approval-required execution did not surface approval control flow."
        )

    assert handler.count == 0
    assert any(
        event.status == "APPROVAL_REQUIRED"
        for event in executor.audit_events
    )


def test_authorized_tool_executes():
    registry = ToolRegistry()
    handler = CountingTool()
    registry.register(counting_descriptor(), handler)
    result = ToolExecutor(registry, allow_policy()).execute(make_call("test.counter"))
    assert result.status == TaskState.SUCCEEDED
    assert result.result["echo"] == "hello"
    assert handler.count == 1


def test_missing_declared_permission_is_rejected():
    registry = ToolRegistry()
    handler = CountingTool()
    registry.register(counting_descriptor(), handler)
    result = ToolExecutor(
        registry, allow_policy()
    ).execute(make_call("test.counter", permissions=()))
    assert result.status == TaskState.FAILED
    assert result.error["code"] == "INVALID_INVOCATION"
    assert handler.count == 0


def test_timeout_does_not_wait_for_full_handler_duration():
    registry = ToolRegistry()
    registry.register(slow_descriptor(), SlowCooperativeTool())
    result = ToolExecutor(registry, allow_policy()).execute(
        make_call("test.slow", arguments={"seconds": 2.0}, timeout_ms=50)
    )
    assert result.status == TaskState.TIMED_OUT


def test_safe_retry_occurs_once():
    registry = ToolRegistry()
    handler = FailingOnceTool()
    registry.register(retry_descriptor(), handler)
    result = ToolExecutor(
        registry, allow_policy()
    ).execute(make_call("test.retry", retry_mode=RetryMode.SAFE))
    assert result.status == TaskState.SUCCEEDED
    assert handler.count == 2


def test_unsafe_retry_is_not_performed():
    registry = ToolRegistry()
    handler = FailingOnceTool()
    registry.register(retry_descriptor(), handler)
    result = ToolExecutor(
        registry, allow_policy()
    ).execute(make_call("test.retry", retry_mode=RetryMode.NONE))
    assert result.status == TaskState.FAILED
    assert handler.count == 1


def test_result_validator_failure_blocks_success():
    class RejectingValidator:
        def validate(self, result):
            return False, ({"check": "deterministic", "passed": False},)

    registry = ToolRegistry()
    registry.register(counting_descriptor(), CountingTool())
    executor = ToolExecutor(
        registry, allow_policy(),
        validators={"test.counter": RejectingValidator()},
    )
    result = executor.execute(make_call("test.counter"))
    assert result.status == TaskState.FAILED
    assert result.error["code"] == "RESULT_VALIDATION_FAILED"


def test_result_validator_success_is_recorded():
    class AcceptingValidator:
        def validate(self, result):
            return True, ({"check": "deterministic", "passed": True},)

    registry = ToolRegistry()
    registry.register(counting_descriptor(), CountingTool())
    executor = ToolExecutor(
        registry, allow_policy(),
        validators={"test.counter": AcceptingValidator()},
    )
    result = executor.execute(make_call("test.counter"))
    assert result.status == TaskState.SUCCEEDED
    assert result.validation_state == "PASSED"
    assert len(result.validation_checks) == 1


def test_timeout_is_audit_logged():
    registry = ToolRegistry()
    registry.register(slow_descriptor(), SlowCooperativeTool())
    executor = ToolExecutor(registry, allow_policy())
    result = executor.execute(
        make_call("test.slow", arguments={"seconds": 2.0}, timeout_ms=25)
    )
    assert result.status == TaskState.TIMED_OUT
    assert any(event.status == "TIMED_OUT" for event in executor.audit_events)


def test_denial_is_audit_logged():
    registry = ToolRegistry()
    registry.register(counting_descriptor(), CountingTool())
    executor = ToolExecutor(registry, PolicyBroker())
    executor.execute(make_call("test.counter"))
    assert any(event.status == "DENIED" for event in executor.audit_events)


def test_unknown_tool_is_fail_closed():
    executor = ToolExecutor(ToolRegistry(), allow_policy())
    result = executor.execute(make_call("does.not.exist"))
    assert result.status == TaskState.FAILED
    assert result.error["code"] == "UNKNOWN_TOOL"


def test_provenance_is_present():
    registry = ToolRegistry()
    registry.register(counting_descriptor(), CountingTool())
    result = ToolExecutor(registry, allow_policy()).execute(make_call("test.counter"))
    assert result.tool == "test.counter"
    assert result.tool_version == "1.0.0"
    assert result.adapter_version == "tool-executor-1.0"


def test_descriptor_timeout_limit_is_enforced():
    registry = ToolRegistry()
    handler = CountingTool()
    registry.register(counting_descriptor(), handler)
    result = ToolExecutor(
        registry, allow_policy()
    ).execute(make_call("test.counter", timeout_ms=60_000))
    assert result.status == TaskState.FAILED
    assert result.error["code"] == "INVALID_INVOCATION"
    assert handler.count == 0


def test_multiple_permissions_are_all_authorized_before_execution():
    class MultiPermissionTool(CountingTool):
        pass

    descriptor = ToolDescriptor(
        tool_id="test.multi",
        version="1.0.0",
        description="Multi-permission deterministic tool.",
        capabilities=("test.multi",),
        arguments=ToolArgumentSchema((
            ToolArgument("value", ToolValueType.STRING, required=True),
        )),
        required_permissions=(
            PermissionScope(PermissionClass.READ, "test:value"),
            PermissionScope(PermissionClass.WRITE, "test:value"),
        ),
    )
    handler = MultiPermissionTool()
    registry = ToolRegistry()
    registry.register(descriptor, handler)

    policy = PolicyBroker(rules=[
        PolicyRule(PermissionClass.READ, "test:*", PermissionDecision.ALLOW),
        PolicyRule(PermissionClass.WRITE, "test:*", PermissionDecision.DENY),
    ])
    call = make_call(
        "test.multi",
        permissions=(
            PermissionScope(PermissionClass.READ, "test:value"),
            PermissionScope(PermissionClass.WRITE, "test:value"),
        ),
    )
    result = ToolExecutor(registry, policy).execute(call)
    assert result.status == TaskState.DENIED
    assert handler.count == 0
    assert len(result.error) > 0

def test_extra_declared_permission_is_rejected():
    registry = ToolRegistry()
    handler = CountingTool()
    registry.register(counting_descriptor(), handler)

    call = make_call(
        "test.counter",
        permissions=(
            PermissionScope(PermissionClass.READ, "test:value"),
            PermissionScope(PermissionClass.WRITE, "test:extra"),
        ),
    )

    result = ToolExecutor(registry, allow_policy()).execute(call)

    assert result.status == TaskState.FAILED
    assert result.error["code"] == "INVALID_INVOCATION"
    assert handler.count == 0
