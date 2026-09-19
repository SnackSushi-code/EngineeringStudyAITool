import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from anne_runtime.audit import AppendOnlyAuditLog
from anne_runtime.cancellation import CancellationToken
from anne_runtime.contracts import PermissionClass, PermissionScope, PermissionDecision, RetryMode, TaskRequest, ToolCall, TaskState
from anne_runtime.execution import ExecutionCoordinator
from anne_runtime.orchestrator import TaskOrchestrator
from anne_runtime.policy import PolicyBroker, PolicyRule
from anne_runtime.tooling import AuthorizedToolRunner, NoopToolExecutor

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "packages" / "schemas"


def make_pair():
    rid, tid = uuid4(), uuid4()
    request=TaskRequest("1.0",rid,tid,"2026-09-18T20:00:00Z","ui","test","normal",uuid4(),("demo.read",),False,None,())
    call=ToolCall("1.0",rid,tid,"demo.noop","execute",{},(PermissionScope(PermissionClass.READ,"workspace/project"),),1000,RetryMode.NONE,"key")
    return request, call

class OrchestratorTests(unittest.TestCase):
    def test_successful_pipeline(self):
        request, call=make_pair()
        broker=PolicyBroker([PolicyRule(PermissionClass.READ,"workspace/project",PermissionDecision.ALLOW)])
        with TemporaryDirectory() as td:
            audit=AppendOnlyAuditLog(Path(td)/"audit.jsonl")
            orch=TaskOrchestrator(ExecutionCoordinator(AuthorizedToolRunner(broker,NoopToolExecutor())),audit,SCHEMAS)
            out=orch.run(request,call)
            self.assertEqual(TaskState.SUCCEEDED,out.state)
            self.assertIsNotNone(out.result)
            self.assertTrue(audit.verify_chain())

    def test_denial_is_terminal_and_audited(self):
        request, call=make_pair()
        with TemporaryDirectory() as td:
            audit=AppendOnlyAuditLog(Path(td)/"audit.jsonl")
            orch=TaskOrchestrator(ExecutionCoordinator(AuthorizedToolRunner(PolicyBroker(),NoopToolExecutor())),audit,SCHEMAS)
            out=orch.run(request,call)
            self.assertEqual(TaskState.DENIED,out.state)
            self.assertEqual("ANN_E_PERMISSION_DENIED",out.error.code)
            record=json.loads((Path(td)/"audit.jsonl").read_text().splitlines()[0])
            self.assertEqual("DENIED",record["outcome"])

    def test_external_cancellation_is_terminal(self):
        request, call=make_pair()
        token=CancellationToken(); token.request("user requested")
        broker=PolicyBroker([PolicyRule(PermissionClass.READ,"workspace/project",PermissionDecision.ALLOW)])
        with TemporaryDirectory() as td:
            audit=AppendOnlyAuditLog(Path(td)/"audit.jsonl")
            orch=TaskOrchestrator(ExecutionCoordinator(AuthorizedToolRunner(broker,NoopToolExecutor())),audit,SCHEMAS)
            out=orch.run(request,call,token)
            self.assertEqual(TaskState.CANCELLED,out.state)

    def test_correlation_mismatch_fails_before_execution(self):
        request, call=make_pair()
        call=ToolCall(call.schema_version,uuid4(),call.task_id,call.tool,call.operation,call.arguments,call.permissions,call.timeout_ms,call.retry_mode,call.idempotency_key)
        with TemporaryDirectory() as td:
            audit=AppendOnlyAuditLog(Path(td)/"audit.jsonl")
            orch=TaskOrchestrator(ExecutionCoordinator(AuthorizedToolRunner(PolicyBroker(),NoopToolExecutor())),audit,SCHEMAS)
            with self.assertRaises(Exception):
                orch.run(request,call)
