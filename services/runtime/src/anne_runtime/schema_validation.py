from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from .errors import ContractValidationError

FORMAT_CHECKER = FormatChecker()


@FORMAT_CHECKER.checks("date-time")
def _date_time(value: object) -> bool:
    if not isinstance(value, str) or ("T" not in value and "t" not in value):
        return False
    from datetime import datetime
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


@FORMAT_CHECKER.checks("uri")
def _uri(value: object) -> bool:
    if not isinstance(value, str) or not value or any(c.isspace() for c in value):
        return False
    from urllib.parse import urlparse
    try:
        return bool(urlparse(value).scheme)
    except ValueError:
        return False


def _load_registry(schema_dir: Path) -> Registry:
    registry = Registry()
    for path in sorted(schema_dir.glob("*.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        resource = Resource.from_contents(
            schema,
            default_specification=DRAFT202012,
        )
        registry = registry.with_resource(schema["$id"], resource)
        registry = registry.with_resource(path.name, resource)
    return registry


def validate_against_schema(
    instance: dict[str, Any],
    schema_name: str,
    schema_dir: Path,
) -> None:
    schema_path = schema_dir / schema_name
    if not schema_path.is_file():
        raise ContractValidationError(f"Schema not found: {schema_path}")

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    registry = _load_registry(schema_dir)
    validator = Draft202012Validator(
        schema,
        registry=registry,
        format_checker=FORMAT_CHECKER,
    )
    errors = sorted(
        validator.iter_errors(instance),
        key=lambda error: list(error.path),
    )
    if errors:
        detail = "; ".join(error.message for error in errors[:5])
        raise ContractValidationError(f"{schema_name}: {detail}")
