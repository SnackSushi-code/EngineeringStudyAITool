from __future__ import annotations

import unittest

from jsonschema import Draft202012Validator, FormatChecker
from validate_schemas import build_registry, load_schemas


class SchemaIntegrityTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.schemas = load_schemas()
        cls.registry = build_registry(cls.schemas)

    def test_expected_schema_count(self):
        self.assertEqual(
            len(self.schemas),
            12,
            "Unexpected Ann-E contract schema count.",
        )

    def test_schema_ids_are_unique(self):
        schema_ids = list(self.schemas.keys())

        self.assertEqual(
            len(schema_ids),
            len(set(schema_ids)),
        )

    def test_all_schemas_are_valid_draft_2020_12(self):
        for schema_id, schema in self.schemas.items():
            with self.subTest(schema=schema_id):
                Draft202012Validator.check_schema(schema)

    def test_all_schema_references_resolve_locally(self):
        for schema_id, schema in self.schemas.items():
            with self.subTest(schema=schema_id):
                validator = Draft202012Validator(
                    schema,
                    registry=self.registry,
                    format_checker=FormatChecker(),
                )

                # Constructing and iterating forces reference resolution.
                list(validator.iter_errors({}))


if __name__ == "__main__":
    unittest.main()
