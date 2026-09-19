import unittest

from anne_runtime.redaction import redact


class RedactionTests(unittest.TestCase):
    def test_nested_secrets_are_redacted(self):
        value = {
            "token": "secret-value",
            "nested": {
                "api_key": "another-secret",
                "normal": "keep",
            },
            "items": [{"password": "hidden"}],
        }

        redacted = redact(value)

        self.assertEqual("[REDACTED]", redacted["token"])
        self.assertEqual(
            "[REDACTED]",
            redacted["nested"]["api_key"],
        )
        self.assertEqual("keep", redacted["nested"]["normal"])
        self.assertEqual(
            "[REDACTED]",
            redacted["items"][0]["password"],
        )
