from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from validate_schemas import FORMAT_CHECKER, build_registry, load_schemas


ROOT = Path(__file__).resolve().parents[2]


UUID_1 = "11111111-1111-4111-8111-111111111111"
UUID_2 = "22222222-2222-4222-8222-222222222222"
UUID_3 = "33333333-3333-4333-8333-333333333333"
TIMESTAMP = "2026-09-18T18:00:00Z"


VALID_FIXTURES: dict[str, dict[str, Any]] = {
    "task-request.schema.json": {
        "schema_version": "1.0",
        "request_id": UUID_1,
        "task_id": UUID_2,
        "created_at": TIMESTAMP,
        "source": "ui",
        "user_intent": "Create a resistor divider schematic",
        "priority": "normal",
        "workspace_id": UUID_3,
        "requested_capabilities": [
            "engineering.kicad.schematic"
        ],
        "approval_context": {
            "required": True,
            "approval_id": None
        },
        "input_artifacts": []
    },

    "task-state.schema.json": {
        "schema_version": "1.0",
        "request_id": UUID_1,
        "task_id": UUID_2,
        "state": "RUNNING",
        "message": "Ann-E is executing the approved task."
    },

    "tool-call.schema.json": {
        "schema_version": "1.0",
        "request_id": UUID_1,
        "task_id": UUID_2,
        "tool": "engineering.kicad",
        "operation": "create_schematic",
        "arguments": {
            "project_name": "resistor-divider"
        },
        "permissions": [
            {
                "class": "WRITE",
                "scope": "workspace:33333333-3333-4333-8333-333333333333"
            }
        ],
        "timeout_ms": 120000,
        "retry": {
            "mode": "safe",
            "idempotency_key": "task-22222222-create-schematic"
        }
    },

    "tool-result.schema.json": {
        "schema_version": "1.0",
        "request_id": UUID_1,
        "task_id": UUID_2,
        "status": "SUCCEEDED",
        "result": {
            "message": "Schematic generated successfully."
        },
        "artifacts": [
            UUID_3
        ],
        "validation": {
            "state": "VALIDATED",
            "checks": [
                {
                    "name": "schema_validation",
                    "passed": True
                }
            ]
        },
        "provenance": {
            "tool": "kicad",
            "tool_version": "9.0.0",
            "adapter_version": "1.0.0"
        },
        "error": None,
        "logs": [
            "Created schematic.",
            "Validation completed."
        ]
    },

    "permission-request.schema.json": {
        "schema_version": "1.0",
        "request_id": UUID_1,
        "principal": {
            "type": "agent",
            "id": "engineer-ann-e"
        },
        "action": {
            "class": "WRITE",
            "target": "workspace:33333333-3333-4333-8333-333333333333"
        },
        "reason": "Create the requested engineering artifact.",
        "task_id": UUID_2
    },

    "permission-decision.schema.json": {
        "schema_version": "1.0",
        "decision": "REQUIRE_APPROVAL",
        "approval_id": UUID_3,
        "policy_version": "1.0.0",
        "expires_at": TIMESTAMP
    },

    "artifact.schema.json": {
        "schema_version": "1.0",
        "artifact_id": UUID_3,
        "content_hash": "a" * 64,
        "media_type": "application/json",
        "creator_task_id": UUID_2,
        "workspace_id": UUID_1,
        "created_at": TIMESTAMP,
        "provenance": {
            "tool": "kicad",
            "version": "9.0.0"
        },
        "validation_state": "VALIDATED",
        "parent_artifacts": [],
        "retention_policy": "project"
    },

    "memory.schema.json": {
        "schema_version": "1.0",
        "memory_id": UUID_1,
        "layer": "ENGINEERING",
        "content": {
            "topic": "KiCad schematic generation",
            "fact": "Generated artifacts must be validated before being marked VALIDATED."
        },
        "source_refs": [
            "internal:engineering-contracts"
        ],
        "confidence": 0.95,
        "created_at": TIMESTAMP,
        "last_validated_at": TIMESTAMP,
        "status": "APPROVED"
    },

    "colony-event.schema.json": {
        "schema_version": "1.0",
        "event_id": UUID_1,
        "timestamp": TIMESTAMP,
        "simulation_tick": 42,
        "type": "TASK_STARTED",
        "agent_id": UUID_2,
        "task_id": UUID_3,
        "payload": {
            "role": "ENGINEER",
            "task": "Create schematic"
        }
    },

    "self-extension-proposal.schema.json": {
        "schema_version": "1.0",
        "proposal_id": UUID_1,
        "requested_capability": "engineering.example_adapter",
        "rationale": "Add a new engineering integration.",
        "source": "https://example.com/project",
        "revision": "abc123",
        "checksum": "a" * 64,
        "license": "BSD-3-Clause",
        "dependency_tree": [
            {
                "name": "example-package",
                "version": "1.0.0"
            }
        ],
        "security_scan": {
            "status": "PASS"
        },
        "tests": {
            "status": "PASS"
        },
        "compatibility": {
            "status": "COMPATIBLE"
        },
        "risk_classification": "LOW",
        "approval_status": "PROPOSED",
        "checkpoint": "checkpoint-001",
        "rollback_target": "stable-001",
        "post_install_health": {
            "status": "NOT_RUN"
        }
    },

    "error.schema.json": {
        "code": "ANN_E_TOOL_TIMEOUT",
        "message": "The engineering tool timed out.",
        "retryable": True,
        "request_id": UUID_1,
        "task_id": UUID_2,
        "details": {
            "tool": "kicad",
            "timeout_ms": 120000
        },
        "recovery": "Retry safely using the same idempotency key."
    },
}


class ComprehensiveContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schemas = load_schemas()
        cls.registry = build_registry(cls.schemas)
        cls.format_checker = FORMAT_CHECKER

    def validator_for(self, filename: str) -> Draft202012Validator:
        schema_id = next(
            schema_id
            for schema_id, schema in self.schemas.items()
            if schema_id.endswith(filename)
        )

        return Draft202012Validator(
            self.schemas[schema_id],
            registry=self.registry,
            format_checker=self.format_checker,
        )

    def test_every_data_schema_has_valid_fixture(self):
        for filename, fixture in VALID_FIXTURES.items():
            with self.subTest(schema=filename):
                validator = self.validator_for(filename)
                errors = list(validator.iter_errors(fixture))

                self.assertEqual(
                    errors,
                    [],
                    "\n".join(error.message for error in errors),
                )

    def test_common_is_definition_only(self):
        self.assertIn(
            "https://ann-e.local/schemas/common.json",
            self.schemas,
        )

    def test_missing_required_property_is_rejected(self):
        for filename, fixture in VALID_FIXTURES.items():
            with self.subTest(schema=filename):
                validator = self.validator_for(filename)
                schema = next(
                    schema
                    for schema_id, schema in self.schemas.items()
                    if schema_id.endswith(filename)
                )

                required = schema.get("required", [])

                if not required:
                    continue

                broken = deepcopy(fixture)
                del broken[required[0]]

                self.assertTrue(
                    list(validator.iter_errors(broken)),
                    f"{filename} accepted missing required property "
                    f"{required[0]!r}",
                )

    def test_unknown_top_level_property_is_rejected(self):
        for filename, fixture in VALID_FIXTURES.items():
            with self.subTest(schema=filename):
                validator = self.validator_for(filename)
                broken = deepcopy(fixture)
                broken["__unexpected_ann_e_test_property"] = True

                self.assertTrue(
                    list(validator.iter_errors(broken)),
                    f"{filename} accepted an unknown property",
                )

    def test_uuid_constraints_are_enforced(self):
        fixture = deepcopy(
            VALID_FIXTURES["task-request.schema.json"]
        )
        fixture["request_id"] = "not-a-uuid"

        validator = self.validator_for("task-request.schema.json")

        self.assertTrue(list(validator.iter_errors(fixture)))

    def test_timestamp_constraints_are_enforced(self):
        fixture = deepcopy(
            VALID_FIXTURES["task-request.schema.json"]
        )
        validator = self.validator_for("task-request.schema.json")

        fixture["created_at"] = "not-a-timestamp"
        self.assertTrue(list(validator.iter_errors(fixture)))

        fixture["created_at"] = "2026-09-18T18:00:00"
        self.assertTrue(list(validator.iter_errors(fixture)))

        fixture["created_at"] = "2026-09-18T18:00:00Z"
        self.assertEqual(
            list(validator.iter_errors(fixture)),
            [],
        )

    def test_enum_constraints_are_enforced(self):
        cases = [
            ("task-request.schema.json", "priority", "INVALID"),
            ("task-state.schema.json", "state", "INVALID"),
            ("permission-decision.schema.json", "decision", "INVALID"),
            ("memory.schema.json", "layer", "INVALID"),
            ("memory.schema.json", "status", "INVALID"),
            ("colony-event.schema.json", "type", "INVALID"),
            (
                "self-extension-proposal.schema.json",
                "risk_classification",
                "INVALID",
            ),
            (
                "self-extension-proposal.schema.json",
                "approval_status",
                "INVALID",
            ),
        ]

        for filename, field, invalid_value in cases:
            with self.subTest(schema=filename, field=field):
                fixture = deepcopy(VALID_FIXTURES[filename])
                fixture[field] = invalid_value

                validator = self.validator_for(filename)

                self.assertTrue(
                    list(validator.iter_errors(fixture))
                )

    def test_tool_timeout_bounds_are_enforced(self):
        fixture = deepcopy(
            VALID_FIXTURES["tool-call.schema.json"]
        )
        validator = self.validator_for("tool-call.schema.json")

        fixture["timeout_ms"] = 0
        self.assertTrue(list(validator.iter_errors(fixture)))

        fixture["timeout_ms"] = 3600001
        self.assertTrue(list(validator.iter_errors(fixture)))

    def test_artifact_hash_format_is_enforced(self):
        fixture = deepcopy(
            VALID_FIXTURES["artifact.schema.json"]
        )
        fixture["content_hash"] = "invalid"

        validator = self.validator_for("artifact.schema.json")

        self.assertTrue(list(validator.iter_errors(fixture)))

    def test_memory_confidence_bounds_are_enforced(self):
        fixture = deepcopy(
            VALID_FIXTURES["memory.schema.json"]
        )
        validator = self.validator_for("memory.schema.json")

        fixture["confidence"] = -0.01
        self.assertTrue(list(validator.iter_errors(fixture)))

        fixture["confidence"] = 1.01
        self.assertTrue(list(validator.iter_errors(fixture)))

    def test_permission_class_is_enforced(self):
        fixture = deepcopy(
            VALID_FIXTURES["permission-request.schema.json"]
        )
        fixture["action"]["class"] = "INVALID"

        validator = self.validator_for(
            "permission-request.schema.json"
        )

        self.assertTrue(list(validator.iter_errors(fixture)))

    def test_self_extension_requires_valid_uri(self):
        fixture = deepcopy(
            VALID_FIXTURES["self-extension-proposal.schema.json"]
        )
        fixture["source"] = "not a uri"

        validator = self.validator_for(
            "self-extension-proposal.schema.json"
        )

        self.assertTrue(list(validator.iter_errors(fixture)))

    def test_error_code_format_is_enforced(self):
        fixture = deepcopy(
            VALID_FIXTURES["error.schema.json"]
        )
        fixture["code"] = "bad-error-code"

        validator = self.validator_for("error.schema.json")

        self.assertTrue(list(validator.iter_errors(fixture)))


if __name__ == "__main__":
    unittest.main()
