import unittest
from pathlib import Path
from uuid import uuid4

from anne_runtime.contracts import (
    PermissionClass,
    PermissionScope,
    RetryMode,
    ToolCall,
)
from anne_runtime.errors import ContractValidationError
from anne_runtime.schema_validation import validate_against_schema


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "packages" / "schemas"


class ContractValidationTests(unittest.TestCase):
    def test_valid_tool_call_against_phase_0_2_schema(self):
        call = ToolCall(
            schema_version="1.0",
            request_id=uuid4(),
            task_id=uuid4(),
            tool="demo.noop",
            operation="execute",
            arguments={},
            permissions=(
                PermissionScope(
                    PermissionClass.READ,
                    "workspace/project/file.txt",
                ),
            ),
            timeout_ms=1000,
            retry_mode=RetryMode.NONE,
            idempotency_key="test-key",
        )

        validate_against_schema(
            call.to_dict(),
            "tool-call.schema.json",
            SCHEMA_DIR,
        )

    def test_invalid_tool_call_rejected(self):
        call = {
            "schema_version": "1.0",
            "request_id": str(uuid4()),
            "task_id": str(uuid4()),
            "tool": "demo.noop",
            "operation": "execute",
            "arguments": {},
            "permissions": [],
            "timeout_ms": 0,
            "retry": {
                "mode": "none",
                "idempotency_key": "x",
            },
        }

        with self.assertRaises(ContractValidationError):
            validate_against_schema(
                call,
                "tool-call.schema.json",
                SCHEMA_DIR,
            )
