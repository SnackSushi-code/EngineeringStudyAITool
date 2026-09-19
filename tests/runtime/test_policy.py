import unittest
from uuid import uuid4

from anne_runtime.contracts import (
    PermissionClass,
    PermissionDecision,
    PermissionRequest,
)
from anne_runtime.errors import PermissionDeniedError
from anne_runtime.policy import PolicyBroker, PolicyRule


def make_request(
    permission_class=PermissionClass.READ,
    target="workspace/project/file.txt",
):
    return PermissionRequest(
        schema_version="1.0",
        request_id=uuid4(),
        principal_type="agent",
        principal_id="test-agent",
        permission_class=permission_class,
        target=target,
        reason="test",
        task_id=uuid4(),
    )


class PolicyTests(unittest.TestCase):
    def test_default_is_deny(self):
        decision = PolicyBroker().evaluate(make_request())
        self.assertEqual(PermissionDecision.DENY, decision.decision)

    def test_explicit_allow(self):
        broker = PolicyBroker([
            PolicyRule(
                PermissionClass.READ,
                "workspace/project/*",
                PermissionDecision.ALLOW,
            )
        ])
        self.assertEqual(
            PermissionDecision.ALLOW,
            broker.evaluate(make_request()).decision,
        )

    def test_approval_is_not_allow(self):
        broker = PolicyBroker([
            PolicyRule(
                PermissionClass.WRITE,
                "workspace/project/*",
                PermissionDecision.ALLOW,
                require_approval=True,
            )
        ])
        self.assertEqual(
            PermissionDecision.REQUIRE_APPROVAL,
            broker.evaluate(
                make_request(PermissionClass.WRITE)
            ).decision,
        )

    def test_authorize_raises_on_deny(self):
        with self.assertRaises(PermissionDeniedError):
            PolicyBroker().authorize(make_request())

    def test_security_sensitive_requires_explicit_rule(self):
        broker = PolicyBroker([
            PolicyRule(
                PermissionClass.READ,
                "*",
                PermissionDecision.ALLOW,
            )
        ])
        decision = broker.evaluate(
            make_request(PermissionClass.SECURITY_SENSITIVE)
        )
        self.assertEqual(PermissionDecision.DENY, decision.decision)
