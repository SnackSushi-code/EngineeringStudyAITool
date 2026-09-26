import unittest
from anne_runtime.cancellation import CancellationRequested, CancellationToken

class CancellationTests(unittest.TestCase):
    def test_token_starts_clear(self):
        token = CancellationToken()
        self.assertFalse(token.is_requested)

    def test_request_is_idempotent(self):
        token = CancellationToken()
        self.assertTrue(token.request("first"))
        self.assertFalse(token.request("second"))
        self.assertEqual("first", token.reason)

    def test_throw_if_requested(self):
        token = CancellationToken()
        token.request("stop")
        with self.assertRaises(CancellationRequested):
            token.throw_if_requested()
