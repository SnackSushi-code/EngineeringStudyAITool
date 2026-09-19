from __future__ import annotations

import multiprocessing
import time
import unittest
from uuid import uuid4

from anne_runtime.worker_process import (
    WorkerProcess,
    WorkerProcessError,
    WorkerProcessState,
)
from anne_runtime.worker_protocol import PROTOCOL_VERSION, WorkerMessage, WorkerMessageType


def echo_handler(message: WorkerMessage) -> dict[str, object]:
    return {"accepted": True, "echo": message.payload}


def slow_handler(message: WorkerMessage) -> dict[str, object]:
    time.sleep(2.0)
    return {"accepted": True}


def make_start(worker_id: str) -> WorkerMessage:
    return WorkerMessage(
        PROTOCOL_VERSION,
        uuid4(),
        uuid4(),
        worker_id,
        WorkerMessageType.START,
        0,
        {"adapter_id": "anne.test", "adapter_version": "0.1.0"},
    )


class WorkerProcessTests(unittest.TestCase):
    def test_real_worker_starts_and_returns_result(self) -> None:
        worker = WorkerProcess(
            worker_id="worker-ipc-001",
            handler=echo_handler,
            context=multiprocessing.get_context("spawn"),
        )
        try:
            ready = worker.start(make_start("worker-ipc-001"), timeout_seconds=3)
            self.assertEqual(ready.message_type, WorkerMessageType.READY)
            result = worker.execute({"value": 42}, timeout_seconds=3)
            self.assertEqual(result.message_type, WorkerMessageType.RESULT)
            self.assertEqual(result.payload["echo"]["value"], 42)
            self.assertEqual(worker.state, WorkerProcessState.READY)
        finally:
            worker.terminate()
            worker.close()

    def test_timeout_is_detected_and_worker_can_be_terminated(self) -> None:
        worker = WorkerProcess(
            worker_id="worker-ipc-002",
            handler=slow_handler,
            context=multiprocessing.get_context("spawn"),
        )
        try:
            worker.start(make_start("worker-ipc-002"), timeout_seconds=3)
            with self.assertRaises(TimeoutError):
                worker.execute({}, timeout_seconds=0.1)
            worker.terminate(grace_seconds=0.1)
            self.assertEqual(worker.state, WorkerProcessState.STOPPED)
        finally:
            worker.terminate()
            worker.close()

    def test_malformed_start_message_is_rejected_before_process_start(self) -> None:
        worker = WorkerProcess(
            worker_id="worker-ipc-003",
            handler=echo_handler,
            context=multiprocessing.get_context("spawn"),
        )
        bad = WorkerMessage(
            "9.9",
            uuid4(),
            uuid4(),
            "worker-ipc-003",
            WorkerMessageType.START,
            0,
            {},
        )
        with self.assertRaises(ValueError):
            worker.start(bad, timeout_seconds=1)
        self.assertEqual(worker.state, WorkerProcessState.NEW)

    def test_worker_identity_mismatch_is_rejected_before_process_start(self) -> None:
        worker = WorkerProcess(
            worker_id="worker-ipc-004",
            handler=echo_handler,
            context=multiprocessing.get_context("spawn"),
        )
        with self.assertRaises(ValueError):
            worker.start(make_start("different-worker"), timeout_seconds=1)
        self.assertEqual(worker.state, WorkerProcessState.NEW)


if __name__ == "__main__":
    unittest.main()
