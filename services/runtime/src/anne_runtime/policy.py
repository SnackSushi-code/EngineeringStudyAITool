from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from fnmatch import fnmatch
from uuid import UUID

from .contracts import (
    PermissionClass,
    PermissionDecision,
    PermissionDecisionRecord,
    PermissionRequest,
)
from .errors import PermissionDeniedError


@dataclass(frozen=True)
class PolicyRule:
    permission_class: PermissionClass
    target_pattern: str
    decision: PermissionDecision
    require_approval: bool = False
    expires_at: str | None = None


class PolicyBroker:
    """Fail-closed authorization broker. It never executes operations."""

    def __init__(
        self,
        rules: list[PolicyRule] | None = None,
        policy_version: str = "0.4.1-dev",
    ):
        self._rules = tuple(rules or ())
        self.policy_version = policy_version

    def evaluate(self, request: PermissionRequest) -> PermissionDecisionRecord:
        matching = [
            rule
            for rule in self._rules
            if rule.permission_class == request.permission_class
            and fnmatch(request.target, rule.target_pattern)
            and not self._expired(rule.expires_at)
        ]

        if not matching:
            return PermissionDecisionRecord(
                decision=PermissionDecision.DENY,
                approval_id=None,
                policy_version=self.policy_version,
                expires_at=None,
            )

        matching.sort(
            key=lambda rule: len(rule.target_pattern),
            reverse=True,
        )
        rule = matching[0]

        if rule.decision == PermissionDecision.DENY:
            return PermissionDecisionRecord(
                decision=PermissionDecision.DENY,
                approval_id=None,
                policy_version=self.policy_version,
                expires_at=rule.expires_at,
            )

        if (
            rule.require_approval
            or rule.decision == PermissionDecision.REQUIRE_APPROVAL
        ):
            return PermissionDecisionRecord(
                decision=PermissionDecision.REQUIRE_APPROVAL,
                approval_id=None,
                policy_version=self.policy_version,
                expires_at=rule.expires_at,
            )

        return PermissionDecisionRecord(
            decision=PermissionDecision.ALLOW,
            approval_id=UUID(int=0),
            policy_version=self.policy_version,
            expires_at=rule.expires_at,
        )

    def authorize(self, request: PermissionRequest) -> PermissionDecisionRecord:
        decision = self.evaluate(request)
        if decision.decision != PermissionDecision.ALLOW:
            raise PermissionDeniedError(
                f"Operation denied by policy: "
                f"{request.permission_class.value} {request.target}"
            )
        return decision

    @staticmethod
    def _expired(expires_at: str | None) -> bool:
        if expires_at is None:
            return False
        try:
            expiry = datetime.fromisoformat(
                expires_at.replace("Z", "+00:00")
            )
        except ValueError:
            return True
        if expiry.tzinfo is None:
            return True
        return expiry <= datetime.now(timezone.utc)
