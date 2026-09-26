import json
import tempfile
import unittest
from pathlib import Path

from anne_runtime.audit import AppendOnlyAuditLog, AuditEvent


class AuditTests(unittest.TestCase):
    def test_append_and_verify_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            log = AppendOnlyAuditLog(path)

            log.append(AuditEvent(
                request_id="req-1",
                task_id="task-1",
                principal="agent:test",
                operation="test.operation",
                policy_decision="ALLOW",
                target="workspace/project",
                outcome="SUCCEEDED",
                details={"token": "must-not-appear"},
            ))
            log.append(AuditEvent(
                request_id="req-2",
                task_id="task-2",
                principal="agent:test",
                operation="test.operation",
                policy_decision="DENY",
                target="workspace/project",
                outcome="DENIED",
            ))

            self.assertTrue(log.verify_chain())

            raw = path.read_text(encoding="utf-8")
            self.assertNotIn("must-not-appear", raw)

            records = [
                json.loads(line)
                for line in raw.splitlines()
            ]
            self.assertEqual(2, len(records))
            self.assertNotEqual(
                records[0]["record_hash"],
                records[1]["record_hash"],
            )

    def test_tampering_breaks_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            log = AppendOnlyAuditLog(path)

            log.append(AuditEvent(
                request_id="req",
                task_id="task",
                principal="user",
                operation="test",
                policy_decision="ALLOW",
                target="x",
                outcome="OK",
            ))

            record = json.loads(path.read_text(encoding="utf-8"))
            record["outcome"] = "ALTERED"
            path.write_text(
                json.dumps(record) + "\n",
                encoding="utf-8",
            )

            self.assertFalse(log.verify_chain())
