from __future__ import annotations

from typing import Any
from pathlib import Path
from uuid import uuid4

import pytest

from anne_runtime.contracts import (
    PermissionScope,
    PermissionClass,
    RetryMode,
    ToolCall,
)
from anne_runtime.execution_supervisor import (
    ExecutionSupervisor,
    SupervisorInvariantError,
    SupervisorState,
)
from anne_runtime.isolation import IsolationPolicy, WorkerDescriptor
from anne_runtime.platform_enforcement import (
    EnforcementCapabilities,
    EnforcementRequest,
    EnforcementPlan,
    PreparedEnforcement,
)
from anne_runtime.worker_protocol import WorkerMessage, WorkerMessageType


class FakeAdapter:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.released = []
        self.terminated = []

    @property
    def capabilities(self) -> EnforcementCapabilities:
        return EnforcementCapabilities(
            platform="test",
            adapter_version="test-1",
            controls=frozenset(),
        )

    def prepare(self, request: EnforcementRequest) -> PreparedEnforcement:
        self.events.append("prepare")

        prepared = PreparedEnforcement(
            handle_id=str(request.execution_id),
            plan=EnforcementPlan(
                platform="test",
                adapter_version="test-1",
                enforced_controls=frozenset(),
                gaps=(),
                workspace_root=request.policy.workspace,
                network_enabled=False,
                environment={},
            ),
        )

        return prepared

    def assign_process(
        self,
        prepared: PreparedEnforcement,
        process_handle: int,
    ) -> None:
        self.events.append("assign")

    def terminate(
        self,
        prepared: PreparedEnforcement,
        *,
        exit_code: int = 1,
    ) -> None:
        self.events.append("platform-terminate")
        self.terminated.append((prepared, exit_code))

    def release(self, prepared: PreparedEnforcement) -> None:
        self.events.append("release")
        self.released.append(prepared)


class FakeWorker:
    def __init__(self, events: list[str], *, timeout: bool = False) -> None:
        self.events = events
        self.timeout = timeout
        self.terminated = False
        self.closed = False

    def start(
        self,
        start_message: WorkerMessage,
        *,
        timeout_seconds: float,
        process_started=None,
    ) -> WorkerMessage:
        self.events.append("worker-process-started")

        if process_started is not None:
            process_started(1234)

        self.events.append("worker-start-message")

        return WorkerMessage(
            protocol_version=start_message.protocol_version,
            request_id=start_message.request_id,
            task_id=start_message.task_id,
            worker_id=start_message.worker_id,
            message_type=WorkerMessageType.READY,
            sequence=0,
            payload={"runtime_api": "test"},
        )

    def execute(
        self,
        payload: dict[str, Any],
        *,
        timeout_seconds: float,
    ) -> WorkerMessage:
        self.events.append("execute")

        if self.timeout:
            raise TimeoutError("simulated timeout")

        raise AssertionError("test worker expected timeout")

    def terminate(self, *, grace_seconds: float = 0.5) -> None:
        self.events.append("worker-terminate")
        self.terminated = True

    def close(self) -> None:
        self.events.append("worker-close")
        self.closed = True


def make_request() -> tuple[ToolCall, WorkerDescriptor, IsolationPolicy]:
    request_id = uuid4()
    task_id = uuid4()

    call = ToolCall(
        schema_version="0.1",
        request_id=request_id,
        task_id=task_id,
        tool="test",
        operation="run",
        arguments={},
        permissions=(
            PermissionScope(
                permission_class=PermissionClass.EXECUTE,
                scope="test",
            ),
        ),
        timeout_ms=5000,
        retry_mode=RetryMode.NONE,
        idempotency_key=str(uuid4()),
    )

    worker = WorkerDescriptor(
        worker_id="test-worker",
        adapter_id="test",
        adapter_version="1",
        runtime_api="1",
    )

    policy = IsolationPolicy(
        workspace=Path("."),
        timeout_seconds=5.0,
    )

    return call, worker, policy


def authorize(supervisor: ExecutionSupervisor):
    call, worker, policy = make_request()

    return supervisor.authorize(
        call,
        worker,
        policy,
        authorization={"authorized": True},
    )


def test_authorization_precedes_enforcement_preparation():
    events: list[str] = []
    adapter = FakeAdapter(events)
    supervisor = ExecutionSupervisor(enforcement_adapter=adapter)

    execution = authorize(supervisor)

    assert execution.state == SupervisorState.AUTHORIZED

    prepared = supervisor.prepare_enforcement(execution.execution_id)

    assert prepared.handle_id == str(execution.execution_id)
    assert events == ["prepare"]


def test_preparation_requires_authorization():
    events: list[str] = []
    adapter = FakeAdapter(events)
    supervisor = ExecutionSupervisor(enforcement_adapter=adapter)

    call, worker, policy = make_request()

    with pytest.raises(SupervisorInvariantError):
        supervisor.prepare_enforcement(uuid4())


def test_process_assignment_occurs_before_worker_start_message():
    events: list[str] = []
    adapter = FakeAdapter(events)
    supervisor = ExecutionSupervisor(enforcement_adapter=adapter)

    execution = authorize(supervisor)
    worker = FakeWorker(events)

    result = supervisor.start_worker(
        execution.execution_id,
        worker,
    )

    assert result.message_type == WorkerMessageType.READY
    assert events.index("assign") < events.index("worker-start-message")


def test_assignment_failure_cleans_up():
    class FailingAdapter(FakeAdapter):
        def assign_process(
            self,
            prepared: PreparedEnforcement,
            process_handle: int,
        ) -> None:
            self.events.append("assign")
            raise RuntimeError("simulated assignment failure")

    events: list[str] = []
    adapter = FailingAdapter(events)
    supervisor = ExecutionSupervisor(enforcement_adapter=adapter)

    execution = authorize(supervisor)
    worker = FakeWorker(events)

    with pytest.raises(RuntimeError, match="simulated assignment failure"):
        supervisor.start_worker(
            execution.execution_id,
            worker,
        )

    final = supervisor.get(execution.execution_id)

    assert worker.terminated
    assert final.state == SupervisorState.TERMINAL
    assert final.cleanup_complete
    assert "release" in events


def test_timeout_uses_platform_termination():
    events: list[str] = []
    adapter = FakeAdapter(events)
    supervisor = ExecutionSupervisor(enforcement_adapter=adapter)

    execution = authorize(supervisor)
    worker = FakeWorker(events, timeout=True)

    supervisor.start_worker(
        execution.execution_id,
        worker,
    )

    with pytest.raises(TimeoutError):
        supervisor.execute_worker(
            execution.execution_id,
            {},
        )

    assert "platform-terminate" in events
    assert "worker-terminate" in events
    assert events.index("platform-terminate") < events.index("worker-terminate")
    assert supervisor.get(execution.execution_id).state == SupervisorState.TIMING_OUT
