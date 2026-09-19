import os
import unittest

from anne_runtime.config import RuntimeConfig


class ConfigTests(unittest.TestCase):
    def test_safe_defaults(self):
        config = RuntimeConfig()
        self.assertFalse(config.privileged_execution_enabled)
        self.assertFalse(config.network_enabled)
        self.assertFalse(config.self_update_enabled)

    def test_environment_loader(self):
        old = os.environ.get("ANN_E_ENVIRONMENT")
        os.environ["ANN_E_ENVIRONMENT"] = "test"
        try:
            self.assertEqual("test", RuntimeConfig.from_environment().environment)
        finally:
            if old is None:
                os.environ.pop("ANN_E_ENVIRONMENT", None)
            else:
                os.environ["ANN_E_ENVIRONMENT"] = old

    def test_privileged_execution_remains_forbidden(self):
        with self.assertRaises(ValueError):
            RuntimeConfig(privileged_execution_enabled=True)
