import unittest

from anne_runtime.adapters import AdapterManifest, AdapterRegistry


class AdapterTests(unittest.TestCase):
    def test_register_and_lookup_is_deterministic(self):
        registry = AdapterRegistry()
        registry.register(AdapterManifest("anne.kicad", "KiCad", "0.1.0", "0.4", ("inspect",)))
        registry.register(AdapterManifest("anne.matlab", "MATLAB", "0.1.0", "0.4", ("inspect",)))
        self.assertEqual(
            ("anne.kicad", "anne.matlab"),
            tuple(item.adapter_id for item in registry.list()),
        )

    def test_duplicate_registration_rejected(self):
        registry = AdapterRegistry()
        manifest = AdapterManifest("anne.test", "Test", "0.1.0", "0.4")
        registry.register(manifest)
        with self.assertRaises(ValueError):
            registry.register(manifest)

    def test_unknown_adapter_fails_closed(self):
        with self.assertRaises(KeyError):
            AdapterRegistry().get("anne.unknown")

    def test_namespace_is_enforced(self):
        registry = AdapterRegistry()
        registry.register(AdapterManifest("external.tool", "Tool", "1.0", "0.4"))
        with self.assertRaises(ValueError):
            registry.validate()
