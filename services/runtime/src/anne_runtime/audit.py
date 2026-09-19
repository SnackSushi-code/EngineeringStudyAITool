from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .redaction import redact

GENESIS = "0" * 64


@dataclass(frozen=True)
class AuditEvent:
    request_id: str
    task_id: str
    principal: str
    operation: str
    policy_decision: str
    target: str
    outcome: str
    artifact_refs: tuple[str, ...] = ()
    details: dict[str, Any] | None = None


class AppendOnlyAuditLog:
    """Application-owned append API with hash chaining."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: AuditEvent) -> dict[str, Any]:
        previous_hash = self._last_hash()
        record = {
            "audit_id": str(uuid4()),
            "request_id": event.request_id,
            "task_id": event.task_id,
            "principal": event.principal,
            "operation": event.operation,
            "policy_decision": event.policy_decision,
            "target": event.target,
            "outcome": event.outcome,
            "artifact_refs": list(event.artifact_refs),
            "details": redact(event.details or {}),
            "previous_hash": previous_hash,
        }
        canonical = json.dumps(
            record,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        record["record_hash"] = hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()

        with self.path.open(
            "a",
            encoding="utf-8",
            newline="\n",
        ) as handle:
            handle.write(
                json.dumps(
                    record,
                    sort_keys=True,
                    ensure_ascii=False,
                )
                + "\n"
            )
        return dict(record)

    def _last_hash(self) -> str:
        if not self.path.exists():
            return GENESIS

        last = None
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last = json.loads(line)

        return last.get("record_hash", GENESIS) if last else GENESIS

    def verify_chain(self) -> bool:
        previous = GENESIS
        if not self.path.exists():
            return True

        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue

                record = json.loads(line)
                if record.get("previous_hash") != previous:
                    return False

                claimed = record.pop("record_hash", None)
                canonical = json.dumps(
                    record,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
                actual = hashlib.sha256(
                    canonical.encode("utf-8")
                ).hexdigest()

                if claimed != actual:
                    return False

                previous = claimed

        return True
