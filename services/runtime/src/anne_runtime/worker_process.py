from __future__ import annotations

import json
import multiprocessing
from dataclasses import dataclass
from enum import StrEnum
from multiprocessing.connection import Connection
from time import monotonic
from typing import Any, Callable
from uuid import UUID

from .worker_protocol import PROTOCOL_VERSION, WorkerMessage, WorkerMessageType


class WorkerProcessError(RuntimeError):
    """Raised when an isolated worker cannot satisfy its process contract."""


class WorkerProcessState(StrEnum):
    NEW = "NEW"
    STARTING = "STARTING"
    READY = "READY"
    RUNNING = "RUNNING"
    CANCELLING = "CANCELLING"
    TERMINATING = "TERMINATING"
    STOPPED = "STOPPED"
    CRASHED = "CRASHED"


@dataclass(frozen=True)
class WorkerProcessSnapshot:
    worker_id: str
    pid: int | None
    state: WorkerProcessState
    exit_code: int | None


WorkerHandler = Callable[[WorkerMessage], dict[str, Any]]


def _encode_message(message: WorkerMessage) -> bytes:
    payload = {
        "protocol_version": message.protocol_version,
        "request_id": str(message.request_id),
        "task_id": str(message.task_id),
        "worker_id": message.worker_id,
        "message_type": message.message_type.value,
        "sequence": message.sequence,
        "payload": message.payload,
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _decode_message(raw: bytes) -> WorkerMessage:
    try:
        value = json.loads(raw.decode("utf-8"))
        return WorkerMessage(
            protocol_version=value["protocol_version"],
            request_id=UUID(value["request_id"]),
            task_id=UUID(value["task_id"]),
            worker_id=value["worker_id"],
            message_type=WorkerMessageType(value["message_type"]),
            sequence=int(value["sequence"]),
            payload=value["payload"],
        )
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkerProcessError("malformed worker IPC message") from exc


def _worker_main(
    connection: Connection,
    worker_id: str,
    handler: WorkerHandler,
    max_message_bytes: int,
) -> None:
    """Minimal worker runtime.

    This process boundary is not itself a security sandbox. Platform
    enforcement is a separate phase.
    """
    try:
        start = _decode_message(connection.recv_bytes())
        start.validate(expected_worker_id=worker_id, max_bytes=max_message_bytes)
        if start.message_type != WorkerMessageType.START or start.sequence != 0:
            raise WorkerProcessError("worker expected START sequence 0")

        connection.send_bytes(
            _encode_message(
                WorkerMessage(
                    PROTOCOL_VERSION,
                    start.request_id,
                    start.task_id,
                    worker_id,
                    WorkerMessageType.READY,
                    0,
                    {"runtime_api": "0.4.7"},
                )
            )
        )

        expected_sequence = 1

        while True:
            message = _decode_message(connection.recv_bytes())
            message.validate(
                expected_worker_id=worker_id,
                max_bytes=max_message_bytes,
            )

            if message.request_id != start.request_id or message.task_id != start.task_id:
                raise WorkerProcessError("worker correlation mismatch")

            if message.sequence != expected_sequence:
                raise WorkerProcessError("worker sequence mismatch")

            if message.message_type == WorkerMessageType.EXECUTE:
                result_payload = handler(message)
                if not isinstance(result_payload, dict):
                    raise WorkerProcessError("worker handler returned a non-object")

                connection.send_bytes(
                    _encode_message(
                        WorkerMessage(
                            PROTOCOL_VERSION,
                            message.request_id,
                            message.task_id,
                            worker_id,
                            WorkerMessageType.RESULT,
                            expected_sequence,
                            result_payload,
                        )
                    )
                )
                expected_sequence += 1
                continue

            if message.message_type == WorkerMessageType.CANCEL:
                connection.send_bytes(
                    _encode_message(
                        WorkerMessage(
                            PROTOCOL_VERSION,
                            message.request_id,
                            message.task_id,
                            worker_id,
                            WorkerMessageType.ERROR,
                            expected_sequence,
                            {"code": "WORKER_CANCELLED"},
                        )
                    )
                )
                return

            if message.message_type == WorkerMessageType.SHUTDOWN:
                return

            raise WorkerProcessError(
                f"unsupported worker message type: {message.message_type}"
            )
    except (EOFError, BrokenPipeError):
        return
    except BaseException as exc:
        try:
            connection.send_bytes(
                _encode_message(
                    WorkerMessage(
                        PROTOCOL_VERSION,
                        start.request_id if "start" in locals() else UUID(int=0),
                        start.task_id if "start" in locals() else UUID(int=0),
                        worker_id,
                        WorkerMessageType.ERROR,
                        0,
                        {"code": "WORKER_FAILED", "exception_type": type(exc).__name__},
                    )
                )
            )
        except Exception:
            pass
        raise
    finally:
        connection.close()


class WorkerProcess:
    """Supervised worker process with bounded JSON IPC.

    The class owns process lifecycle and IPC framing. It does not claim OS
    sandboxing, filesystem isolation, network isolation, or resource-limit
    enforcement; those require platform enforcement adapters.
    """

    def __init__(
        self,
        *,
        worker_id: str,
        handler: WorkerHandler,
        max_message_bytes: int = 1_048_576,
        context: multiprocessing.context.BaseContext | None = None,
    ) -> None:
        if not worker_id.strip():
            raise ValueError("worker_id cannot be empty")
        if max_message_bytes <= 0:
            raise ValueError("max_message_bytes must be positive")

        self._worker_id = worker_id
        self._handler = handler
        self._max_message_bytes = max_message_bytes
        self._context = context or multiprocessing.get_context("spawn")
        self._parent: Connection | None = None
        self._process: multiprocessing.Process | None = None
        self._state = WorkerProcessState.NEW
        self._exit_code: int | None = None
        self._request_id: UUID | None = None
        self._task_id: UUID | None = None
        self._next_sequence = 1
        self._next_sequence = 1

    @property
    def state(self) -> WorkerProcessState:
        return self._state

    def snapshot(self) -> WorkerProcessSnapshot:
        return WorkerProcessSnapshot(
            worker_id=self._worker_id,
            pid=self._process.pid if self._process else None,
            state=self._state,
            exit_code=self._process.exitcode if self._process else self._exit_code,
        )

    def start(self, start_message: WorkerMessage, *, timeout_seconds: float) -> WorkerMessage:
        if self._state != WorkerProcessState.NEW:
            raise WorkerProcessError("worker can only be started once")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        start_message.validate(
            expected_worker_id=self._worker_id,
            max_bytes=self._max_message_bytes,
        )
        if start_message.message_type != WorkerMessageType.START:
            raise WorkerProcessError("worker start requires START message")
        if start_message.sequence != 0:
            raise WorkerProcessError("worker START sequence must be zero")

        parent, child = self._context.Pipe(duplex=True)
        self._parent = parent
        self._request_id = start_message.request_id
        self._task_id = start_message.task_id
        self._next_sequence = 1
        self._state = WorkerProcessState.STARTING

        process = self._context.Process(
            target=_worker_main,
            args=(child, self._worker_id, self._handler, self._max_message_bytes),
            name=f"anne-worker-{self._worker_id}",
        )
        process.daemon = True
        self._process = process
        process.start()
        child.close()

        self._send(start_message)
        ready = self._receive(timeout_seconds)
        self._validate_response(ready, WorkerMessageType.READY, 0)
        self._state = WorkerProcessState.READY
        return ready

    def execute(self, payload: dict[str, Any], *, timeout_seconds: float) -> WorkerMessage:
        if self._state != WorkerProcessState.READY:
            raise WorkerProcessError("worker must be READY before execution")
        message = self._build_message(
            WorkerMessageType.EXECUTE,
            sequence=self._consume_sequence(),
            payload=payload,
        )
        self._state = WorkerProcessState.RUNNING
        self._send(message)
        result = self._receive(timeout_seconds)
        self._validate_response(result, WorkerMessageType.RESULT, result.sequence)
        self._state = WorkerProcessState.READY
        return result

    def cancel(self, *, timeout_seconds: float = 2.0) -> WorkerMessage:
        if self._state not in {WorkerProcessState.READY, WorkerProcessState.RUNNING}:
            raise WorkerProcessError("worker cannot be cancelled from its current state")
        self._state = WorkerProcessState.CANCELLING
        message = self._build_message(
            WorkerMessageType.CANCEL,
            sequence=self._consume_sequence(),
            payload={"reason": "supervisor_cancelled"},
        )
        self._send(message)
        response = self._receive(timeout_seconds)
        self._validate_response(response, WorkerMessageType.ERROR, 2)
        self._state = WorkerProcessState.STOPPED
        return response

    def terminate(self, *, grace_seconds: float = 0.5) -> None:
        if self._process is None:
            self._state = WorkerProcessState.STOPPED
            return

        if not self._process.is_alive():
            self._exit_code = self._process.exitcode
            self._state = (
                WorkerProcessState.STOPPED
                if self._process.exitcode in (0, None)
                else WorkerProcessState.CRASHED
            )
            return

        self._state = WorkerProcessState.TERMINATING
        try:
            if self._parent is not None:
                self._send(
                    self._build_message(
                        WorkerMessageType.SHUTDOWN,
                        sequence=self._consume_sequence(),
                        payload={},
                    )
                )
        except (BrokenPipeError, EOFError, OSError, WorkerProcessError):
            pass

        self._process.join(max(0.0, grace_seconds))

        if self._process.is_alive():
            self._process.terminate()
            self._process.join(max(0.1, grace_seconds))

        self._exit_code = self._process.exitcode
        self._state = WorkerProcessState.STOPPED

    def close(self) -> None:
        if self._parent is not None:
            self._parent.close()
            self._parent = None

    def _send(self, message: WorkerMessage) -> None:
        if self._parent is None:
            raise WorkerProcessError("worker IPC is not connected")
        raw = _encode_message(message)
        if len(raw) > self._max_message_bytes:
            raise WorkerProcessError("worker IPC message exceeds configured limit")
        try:
            self._parent.send_bytes(raw)
        except (BrokenPipeError, EOFError, OSError) as exc:
            self._state = WorkerProcessState.CRASHED
            raise WorkerProcessError("worker IPC send failed") from exc

    def _receive(self, timeout_seconds: float) -> WorkerMessage:
        if self._parent is None:
            raise WorkerProcessError("worker IPC is not connected")
        deadline = monotonic() + timeout_seconds
        remaining = max(0.0, deadline - monotonic())

        if not self._parent.poll(remaining):
            if self._process is not None and not self._process.is_alive():
                self._exit_code = self._process.exitcode
                self._state = WorkerProcessState.CRASHED
                raise WorkerProcessError("worker exited before sending a response")
            raise TimeoutError("worker IPC response timed out")

        try:
            raw = self._parent.recv_bytes()
        except (EOFError, OSError) as exc:
            self._state = WorkerProcessState.CRASHED
            raise WorkerProcessError("worker IPC receive failed") from exc

        if len(raw) > self._max_message_bytes:
            self._state = WorkerProcessState.CRASHED
            raise WorkerProcessError("worker IPC response exceeds configured limit")

        return _decode_message(raw)

    def _validate_response(
        self,
        message: WorkerMessage,
        expected_type: WorkerMessageType,
        expected_sequence: int,
    ) -> None:
        message.validate(
            expected_worker_id=self._worker_id,
            max_bytes=self._max_message_bytes,
        )
        if message.request_id != self._request_id or message.task_id != self._task_id:
            self._state = WorkerProcessState.CRASHED
            raise WorkerProcessError("worker response correlation mismatch")
        if message.message_type != expected_type:
            self._state = WorkerProcessState.CRASHED
            raise WorkerProcessError("unexpected worker response type")
        if message.sequence != expected_sequence:
            self._state = WorkerProcessState.CRASHED
            raise WorkerProcessError("unexpected worker response sequence")

    def _consume_sequence(self) -> int:
        sequence = self._next_sequence
        self._next_sequence += 1
        return sequence

    def _consume_sequence(self) -> int:
        sequence = self._next_sequence
        self._next_sequence += 1
        return sequence

    def _build_message(
        self,
        message_type: WorkerMessageType,
        *,
        sequence: int,
        payload: dict[str, Any],
    ) -> WorkerMessage:
        if self._request_id is None or self._task_id is None:
            raise WorkerProcessError("worker request context is not initialized")
        return WorkerMessage(
            PROTOCOL_VERSION,
            self._request_id,
            self._task_id,
            self._worker_id,
            message_type,
            sequence,
            payload,
        )
