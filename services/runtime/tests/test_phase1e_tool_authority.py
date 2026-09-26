from __future__ import annotations
import json
from uuid import uuid4
import pytest
from anne_runtime.contracts import PermissionClass, PermissionScope, RetryMode
from anne_runtime.intelligence_contracts import IntelligenceToolProposal
from anne_runtime.intelligence_tool_authority import (
    ToolAuthorityError,
    ToolAuthorityResolver,
    ToolCapabilityCatalog,
)
from anne_runtime.tool_contracts import (
    ToolArgument,
    ToolArgumentSchema,
    ToolDescriptor,
    ToolValueType,
)
from anne_runtime.tool_registry import ToolRegistry


def registry():
    r = ToolRegistry()
    r.register(
        ToolDescriptor(
            tool_id="files.read",
            version="2.1",
            description="Read a file",
            capabilities=("READ",),
            arguments=ToolArgumentSchema(
                arguments=(
                    ToolArgument(
                        name="path",
                        value_type=ToolValueType.STRING,
                        required=True,
                        description="File path",
                    ),
                )
            ),
            required_permissions=(PermissionScope(PermissionClass.READ, "workspace"),),
            retry_mode=RetryMode.NONE,
            max_timeout_ms=2500,
        ),
        lambda context, arguments: {"ok": True},
    )
    return r


def proposal(tool="files.read", args=None):
    return IntelligenceToolProposal(
        request_id=uuid4(),
        task_id=uuid4(),
        tool=tool,
        operation="read",
        arguments=args or {"path": "notes.txt"},
    )


def test_valid_resolution_uses_descriptor_authority():
    c = ToolAuthorityResolver(registry()).resolve(proposal()).call
    assert c.timeout_ms == 2500
    assert c.retry_mode is RetryMode.NONE
    assert c.permissions == (PermissionScope(PermissionClass.READ, "workspace"),)
    assert c.idempotency_key


def test_unknown_tool_is_rejected():
    with pytest.raises(ToolAuthorityError, match="Unknown tool"):
        ToolAuthorityResolver(registry()).resolve(proposal("missing.tool"))


def test_invalid_arguments_are_rejected():
    with pytest.raises(ToolAuthorityError):
        ToolAuthorityResolver(registry()).resolve(proposal(args={"wrong": "x"}))


def test_idempotency_is_runtime_generated():
    r = ToolAuthorityResolver(registry())
    assert (
        r.resolve(proposal()).call.idempotency_key
        != r.resolve(proposal()).call.idempotency_key
    )


def test_catalog_excludes_authority_fields():
    payload = json.dumps(ToolCapabilityCatalog(registry()).snapshot())
    assert "files.read" in payload
    for forbidden in (
        "permissions",
        "timeout_ms",
        "retry_mode",
        "idempotency_key",
        "required_permissions",
        "max_timeout_ms",
    ):
        assert forbidden not in payload


def test_model_receives_sanitized_tool_catalog():
    import json

    from anne_runtime.contracts import PermissionClass, PermissionScope
    from anne_runtime.deterministic_provider import DeterministicModelProvider
    from anne_runtime.intelligence_contracts import IntelligenceRequest
    from anne_runtime.intelligence_orchestrator import IntelligenceOrchestrator
    from anne_runtime.intelligence_tool_authority import ToolCapabilityCatalog
    from anne_runtime.model_router import ModelRouter
    from anne_runtime.model_service import ModelService
    from anne_runtime.provider_registry import ProviderRegistry
    from anne_runtime.tool_contracts import (
        RetryMode,
        ToolArgument,
        ToolArgumentSchema,
        ToolDescriptor,
        ToolValueType,
    )
    from anne_runtime.tool_registry import ToolRegistry

    captured = []

    def responder(model_request):
        captured.append(model_request)
        return json.dumps(
            {
                "contract_version": "1.0",
                "decision_type": "FINAL_RESPONSE",
                "response_text": "ok",
            }
        )

    registry = ToolRegistry()
    registry.register(
        ToolDescriptor(
            tool_id="catalog.test",
            version="1.0",
            description="Catalog test tool",
            capabilities=("filesystem",),
            arguments=ToolArgumentSchema(
                arguments=(
                    ToolArgument(
                        name="path",
                        value_type=ToolValueType.STRING,
                        required=True,
                        description="Path to inspect",
                    ),
                )
            ),
            required_permissions=(
                PermissionScope(
                    permission_class=PermissionClass.READ,
                    scope="filesystem",
                ),
            ),
            retry_mode=RetryMode.NONE,
            max_timeout_ms=2500,
        ),
        lambda call: None,
    )

    providers = ProviderRegistry()
    providers.register(DeterministicModelProvider(responder=responder))

    service = ModelService(
        ModelRouter(
            providers,
            default_provider_id="deterministic",
            default_model="deterministic-v1",
        )
    )

    orchestrator = IntelligenceOrchestrator(
        service,
        capability_catalog=ToolCapabilityCatalog(registry),
    )

    request = IntelligenceRequest(
        request_id=uuid4(),
        task_id=uuid4(),
        user_intent="inspect",
        conversation=(),
        metadata={},
    )

    orchestrator.process(request)

    assert len(captured) == 1

    metadata = captured[0].metadata
    assert "anne.tool_catalog" in metadata

    catalog = json.loads(metadata["anne.tool_catalog"])

    assert len(catalog) == 1
    entry = catalog[0]

    assert entry["tool_id"] == "catalog.test"
    assert entry["version"] == "1.0"
    assert entry["description"] == "Catalog test tool"
    assert entry["capabilities"] == ["filesystem"]
    assert entry["arguments"]["required"] == ["path"]

    for forbidden in (
        "permissions",
        "required_permissions",
        "timeout_ms",
        "max_timeout_ms",
        "retry_mode",
        "idempotency_key",
    ):
        assert forbidden not in entry


def test_model_cannot_supply_authority_fields():
    import json

    from anne_runtime.deterministic_provider import DeterministicModelProvider
    from anne_runtime.intelligence_contracts import IntelligenceRequest
    from anne_runtime.intelligence_orchestrator import (
        IntelligenceOrchestrationError,
        IntelligenceOrchestrator,
    )
    from anne_runtime.model_router import ModelRouter
    from anne_runtime.model_service import ModelService
    from anne_runtime.provider_registry import ProviderRegistry

    def make_service(content):
        def responder(model_request):
            return content

        providers = ProviderRegistry()
        providers.register(DeterministicModelProvider(responder=responder))

        return ModelService(
            ModelRouter(
                providers,
                default_provider_id="deterministic",
                default_model="deterministic-v1",
            )
        )

    request = IntelligenceRequest(
        request_id=uuid4(),
        task_id=uuid4(),
        user_intent="test",
        conversation=(),
        metadata={},
    )

    fields = (
        "permissions",
        "timeout_ms",
        "retry_mode",
        "idempotency_key",
        "schema_version",
    )

    for field in fields:
        payload = {
            "decision_type": "TOOL_PROPOSAL",
            "tool_call": {
                "request_id": str(request.request_id),
                "task_id": str(request.task_id),
                "tool": "catalog.test",
                "operation": "read",
                "arguments": {},
                field: "attacker",
            },
        }

        with pytest.raises(IntelligenceOrchestrationError) as exc_info:
            IntelligenceOrchestrator(make_service(json.dumps(payload))).process(request)

        assert str(exc_info.value) == "model response contains an invalid tool_call"
