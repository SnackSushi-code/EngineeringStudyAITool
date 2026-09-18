from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "packages" / "schemas"


def _is_date_time(value: object) -> bool:
    if not isinstance(value, str):
        return False

    try:
        from datetime import datetime
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return "T" in value or "t" in value
    except ValueError:
        return False


def _is_uri(value: object) -> bool:
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        return False

    try:
        parsed = urlparse(value)
    except ValueError:
        return False

    return bool(parsed.scheme)


FORMAT_CHECKER = FormatChecker()


@FORMAT_CHECKER.checks("date-time")
def _check_date_time(value: object) -> bool:
    return _is_date_time(value)


@FORMAT_CHECKER.checks("uri")
def _check_uri(value: object) -> bool:
    return _is_uri(value)


def load_schemas() -> dict[str, dict[str, Any]]:
    schemas: dict[str, dict[str, Any]] = {}

    for path in sorted(SCHEMA_DIR.glob("*.json")):
        with path.open("r", encoding="utf-8") as handle:
            document = json.load(handle)

        if not isinstance(document, dict):
            raise ValueError(f"{path} does not contain a JSON object")

        schema_id = document.get("$id")

        if not isinstance(schema_id, str) or not schema_id:
            raise ValueError(f"{path} does not define a valid $id")

        if schema_id in schemas:
            raise ValueError(f"Duplicate schema $id detected: {schema_id}")

        schemas[schema_id] = document

    return schemas


def build_registry(
    schemas: dict[str, dict[str, Any]],
) -> Registry:
    registry = Registry()

    for schema_id, schema in schemas.items():
        resource = Resource.from_contents(
            schema,
            default_specification=DRAFT202012,
        )

        registry = registry.with_resource(
            schema_id,
            resource,
        )

    return registry


def validate_all_schemas() -> None:
    schemas = load_schemas()

    if not schemas:
        raise AssertionError(
            f"No JSON schemas found in {SCHEMA_DIR}"
        )

    registry = build_registry(schemas)

    for schema_id, schema in schemas.items():
        Draft202012Validator.check_schema(schema)

        validator = Draft202012Validator(
            schema,
            registry=registry,
            format_checker=FORMAT_CHECKER,
        )

        list(validator.iter_errors({}))

        print(f"VALID: {schema_id}")

    print()
    print("Registered format checkers:")
    print("  date-time:", "date-time" in FORMAT_CHECKER.checkers)
    print("  uri:", "uri" in FORMAT_CHECKER.checkers)
    print("  uuid:", "uuid" in FORMAT_CHECKER.checkers)

    print()
    print("All schemas passed structural validation.")


if __name__ == "__main__":
    validate_all_schemas()
