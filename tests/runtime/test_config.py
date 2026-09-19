import unittest

from anne_runtime.config import RuntimeConfig


class RuntimeConfigTests(unittest.TestCase):
    def test_privileged_execution_is_disabled_by_default(self):
        config = RuntimeConfig()
        self.assertFalse(config.privileged_execution_enabled)
        self.assertFalse(config.network_enabled)
        self.assertFalse(config.self_update_enabled)

    def test_privileged_execution_cannot_be_enabled_in_this_phase(self):
        with self.assertRaises(ValueError):
            RuntimeConfig(privileged_execution_enabled=True)
