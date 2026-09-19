import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from anne_runtime.audit import AppendOnlyAuditLog
from anne_runtime.cancellation import CancellationToken
from anne_runtime.contracts import PermissionClass, PermissionScope, PermissionDecision, RetryMode, ToolCall
from anne_runtime.execution import ExecutionCoordinator
from anne_runtime.policy import PolicyBroker, PolicyRule
from anne_runtime.tooling import AuthorizedToolRunner, NoopToolExecutor

class ExecutionTests(unittest.TestCase):
    def test_controlled_execution_path(self):
        call=ToolCall("1.0",uuid4(),uuid4(),"demo.noop","execute",{},(PermissionScope(PermissionClass.READ,"workspace/project"),),1000,RetryMode.NONE,"key")
        runner=AuthorizedToolRunner(PolicyBroker([PolicyRule(PermissionClass.READ,"workspace/project",PermissionDecision.ALLOW)]),NoopToolExecutor())
        result=ExecutionCoordinator(runner).execute(call,CancellationToken())
        self.assertFalse(result.result["executed"])

    def test_cancelled_before_execution(self):
        call=ToolCall("1.0",uuid4(),uuid4(),"demo.noop","execute",{},(PermissionScope(PermissionClass.READ,"workspace/project"),),1000,RetryMode.NONE,"key")
        token=CancellationToken(); token.request("test")
        runner=AuthorizedToolRunner(PolicyBroker([PolicyRule(PermissionClass.READ,"workspace/project",PermissionDecision.ALLOW)]),NoopToolExecutor())
        with self.assertRaises(Exception):
            ExecutionCoordinator(runner).execute(call,token)
