import unittest
from anne_runtime.retry import RetryPolicy, run_with_retry
from anne_runtime.contracts import RetryMode

class RetryTests(unittest.TestCase):
    def test_none_runs_once(self):
        calls=[]
        with self.assertRaises(RuntimeError):
            run_with_retry(lambda: (calls.append(1), (_ for _ in ()).throw(RuntimeError("x")))[1], RetryPolicy())
        self.assertEqual(1, len(calls))

    def test_safe_retry_requires_explicit_policy(self):
        calls=[]
        def op():
            calls.append(1)
            if len(calls)==1: raise TimeoutError("retry")
            return "ok"
        self.assertEqual("ok", run_with_retry(op, RetryPolicy(RetryMode.SAFE, 2), is_retryable=lambda e: isinstance(e, TimeoutError)))
        self.assertEqual(2, len(calls))
