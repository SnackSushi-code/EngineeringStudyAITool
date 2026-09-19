from __future__ import annotations

import unittest

from anne_runtime.adapter_execution import MockEngineeringAdapter
from anne_runtime.adapters import AdapterRegistry


class AdapterRegistryBoundaryTests(unittest.TestCase):
    def test_capability_declaration_does_not_create_authorization(self):
        registry = AdapterRegistry()
        adapter = MockEngineeringAdapter()

        registry.register(adapter)

        manifest = registry.get("anne.mock.engineering")

        self.assertEqual(
            manifest.adapter_id,
            "anne.mock.engineering",
        )
        self.assertEqual(
            manifest.operations,
            ("generate_artifact",),
        )

        # Registry exposes capability metadata/routing only.
        # It does not expose an authorization decision.
        self.assertFalse(hasattr(registry, "authorize"))
        self.assertFalse(hasattr(registry, "evaluate"))

    def test_worker_can_be_resolved_without_authorization(self):
        registry = AdapterRegistry()
        adapter = MockEngineeringAdapter()

        registry.register(adapter)

        worker = registry.get_worker(
            "anne.mock.engineering"
        )

        self.assertIs(worker, adapter)


if __name__ == "__main__":
    unittest.main()
