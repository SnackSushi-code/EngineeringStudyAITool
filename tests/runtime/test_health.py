import tempfile
import unittest
from pathlib import Path

from anne_runtime.adapters import AdapterRegistry
from anne_runtime.config import RuntimeConfig
from anne_runtime.health import check_runtime_health


class HealthTests(unittest.TestCase):
    def test_health_reports_required_scaffolding(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            schemas = root / "schemas"
            schemas.mkdir()
            health = check_runtime_health(
                RuntimeConfig(schema_dir=schemas, audit_path=root / "data" / "audit.jsonl"),
                AdapterRegistry(),
            )
            self.assertTrue(health.ok)
            self.assertTrue(all(check.ok for check in health.checks))
