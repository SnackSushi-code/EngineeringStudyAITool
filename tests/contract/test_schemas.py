from pathlib import Path
import json
import unittest
from jsonschema import Draft202012Validator, FormatChecker, RefResolver

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "packages" / "schemas"


class ContractSchemaTests(unittest.TestCase):
    def validator(self, filename):
        schema_path = SCHEMA_DIR / filename
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        store = {}
        for path in SCHEMA_DIR.glob("*.json"):
            document = json.loads(path.read_text(encoding="utf-8"))
            if "$id" in document:
                store[document["$id"]] = document

        resolver = RefResolver(
            base_uri=schema_path.as_uri(),
            referrer=schema,
            store=store,
        )

        return Draft202012Validator(
            schema,
            resolver=resolver,
            format_checker=FormatChecker(),
        )

    def test_valid_task_request(self):
        data = json.loads(
            (Path(__file__).parent / "fixtures/valid/task-request.json")
            .read_text(encoding="utf-8")
        )

        errors = list(
            self.validator("task-request.schema.json").iter_errors(data)
        )

        self.assertEqual(errors, [])

    def test_invalid_task_request_rejected(self):
        data = json.loads(
            (
                Path(__file__).parent
                / "fixtures/invalid/task-request-missing-task-id.json"
            ).read_text(encoding="utf-8")
        )

        errors = list(
            self.validator("task-request.schema.json").iter_errors(data)
        )

        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
