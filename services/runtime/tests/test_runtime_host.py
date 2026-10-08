from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from uuid import uuid4

from anne_runtime.runtime_host import _dispatch, run_host
from anne_runtime.runtime_protocol import (
    RuntimeRequest,
    RuntimeResponse,
    decode_request,
    decode_response,
    encode_message,
)


def test_health_dispatch() -> None:
    request = RuntimeRequest(
        request_id=str(uuid4()),
        task_id=str(uuid4()),
        operation="health",
        payload={},
    )

    response = _dispatch(request)

    assert response.request_id == request.request_id
    assert response.task_id == request.task_id
    assert response.status == "completed"
    assert response.payload["healthy"] is True
    assert response.payload["runtime_version"]


def test_unsupported_operation_returns_failed_response() -> None:
    request = RuntimeRequest(
        request_id=str(uuid4()),
        task_id=str(uuid4()),
        operation="does_not_exist",
        payload={},
    )

    response = _dispatch(request)

    assert response.request_id == request.request_id
    assert response.task_id == request.task_id
    assert response.status == "failed"

    error = response.payload["error"]

    assert error["code"] == "ANN_E_UNSUPPORTED_OPERATION"
    assert "does_not_exist" in error["message"]


def test_host_process_health_round_trip() -> None:
    request = RuntimeRequest(
        request_id=str(uuid4()),
        task_id=str(uuid4()),
        operation="health",
        payload={},
    )

    result = _run_host_process(
        encode_message(request)
    )

    assert result.returncode == 0

    lines = [
        line
        for line in result.stdout.splitlines()
        if line.strip()
    ]

    assert len(lines) == 1

    response = decode_response(lines[0])

    assert response.request_id == request.request_id
    assert response.task_id == request.task_id
    assert response.status == "completed"
    assert response.payload["healthy"] is True
    assert result.stderr == ""


def test_host_process_unsupported_operation() -> None:
    request = RuntimeRequest(
        request_id=str(uuid4()),
        task_id=str(uuid4()),
        operation="not_supported",
        payload={},
    )

    result = _run_host_process(
        encode_message(request)
    )

    assert result.returncode == 0

    lines = [
        line
        for line in result.stdout.splitlines()
        if line.strip()
    ]

    assert len(lines) == 1

    response = decode_response(lines[0])

    assert response.request_id == request.request_id
    assert response.task_id == request.task_id
    assert response.status == "failed"

    error = response.payload["error"]

    assert error["code"] == "ANN_E_UNSUPPORTED_OPERATION"


def test_host_process_multiple_requests() -> None:
    requests = [
        RuntimeRequest(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            operation="health",
            payload={},
        ),
        RuntimeRequest(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            operation="health",
            payload={"detail": True},
        ),
        RuntimeRequest(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            operation="unknown",
            payload={},
        ),
    ]

    input_data = "\n".join(
        encode_message(request)
        for request in requests
    ) + "\n"

    result = _run_host_process(input_data)

    assert result.returncode == 0

    lines = [
        line
        for line in result.stdout.splitlines()
        if line.strip()
    ]

    assert len(lines) == len(requests)

    responses = [
        decode_response(line)
        for line in lines
    ]

    response_by_id = {
        (response.request_id, response.task_id): response
        for response in responses
    }

    request_by_id = {
        (request.request_id, request.task_id): request
        for request in requests
    }

    assert set(response_by_id.keys()) == set(request_by_id.keys())

    first_response = response_by_id[
        (requests[0].request_id, requests[0].task_id)
    ]

    second_response = response_by_id[
        (requests[1].request_id, requests[1].task_id)
    ]

    third_response = response_by_id[
        (requests[2].request_id, requests[2].task_id)
    ]

    assert first_response.status == "completed"
    assert second_response.status == "completed"
    assert third_response.status == "failed"


def test_host_processes_requests_concurrently(monkeypatch) -> None:
    requests = [
        RuntimeRequest(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            operation="health",
            payload={},
        ),
        RuntimeRequest(
            request_id=str(uuid4()),
            task_id=str(uuid4()),
            operation="health",
            payload={},
        ),
    ]

    active_requests = 0
    max_active_requests = 0
    state_lock = threading.Lock()

    def fake_application(*, repository_root):
        return object()

    def fake_handle_line(*, raw_line, application):
        nonlocal active_requests, max_active_requests

        with state_lock:
            active_requests += 1
            max_active_requests = max(
                max_active_requests,
                active_requests,
            )

        try:
            time.sleep(0.15)

            request = decode_request(raw_line)

            return RuntimeResponse(
                request_id=request.request_id,
                task_id=request.task_id,
                status="completed",
                payload={"healthy": True},
            )
        finally:
            with state_lock:
                active_requests -= 1

    monkeypatch.setattr(
        "anne_runtime.runtime_host.RuntimeApplication",
        fake_application,
    )

    monkeypatch.setattr(
        "anne_runtime.runtime_host._handle_line",
        fake_handle_line,
    )

    input_data = "\n".join(
        encode_message(request)
        for request in requests
    ) + "\n"

    class FakeStdin:
        def __iter__(self):
            return iter(input_data.splitlines(True))

    output_lines: list[str] = []

    class FakeStdout:
        def write(self, value):
            output_lines.append(value)
            return len(value)

        def flush(self):
            pass

    monkeypatch.setattr(
        "anne_runtime.runtime_host.sys",
        type(
            "FakeSys",
            (),
            {
                "stdin": FakeStdin(),
                "stdout": FakeStdout(),
            },
        ),
    )

    start = time.perf_counter()

    result = run_host()

    elapsed = time.perf_counter() - start

    assert result == 0
    assert max_active_requests >= 2
    assert elapsed < 0.28

    responses = [
        decode_response(line)
        for line in output_lines
        if line.strip()
    ]

    assert len(responses) == len(requests)

    response_ids = {
        (response.request_id, response.task_id)
        for response in responses
    }

    request_ids = {
        (request.request_id, request.task_id)
        for request in requests
    }

    assert response_ids == request_ids


def test_host_does_not_write_diagnostics_to_stdout() -> None:
    request = RuntimeRequest(
        request_id=str(uuid4()),
        task_id=str(uuid4()),
        operation="health",
        payload={},
    )

    result = _run_host_process(
        encode_message(request)
    )

    assert result.returncode == 0

    stdout_lines = [
        line
        for line in result.stdout.splitlines()
        if line.strip()
    ]

    assert len(stdout_lines) == 1

    decoded = json.loads(stdout_lines[0])

    assert decoded["type"] == "response"
    assert decoded["request_id"] == request.request_id
    assert decoded["task_id"] == request.task_id


def test_host_rejects_unknown_protocol_fields() -> None:
    request_id = str(uuid4())
    task_id = str(uuid4())

    raw = json.dumps(
        {
            "protocol_version": "1.0",
            "type": "request",
            "request_id": request_id,
            "task_id": task_id,
            "operation": "health",
            "payload": {},
            "permissions": ["admin"],
        }
    )

    result = _run_host_process(raw)

    assert result.returncode == 0

    lines = [
        line
        for line in result.stdout.splitlines()
        if line.strip()
    ]

    assert len(lines) == 1

    response = decode_response(lines[0])

    assert response.request_id == request_id
    assert response.task_id == task_id
    assert response.status == "failed"

    error = response.payload["error"]

    assert error["code"] == "ANN_E_PROTOCOL_ERROR"
    assert "unknown protocol fields" in error["message"]


def test_host_handles_malformed_json() -> None:
    result = _run_host_process(
        "{this-is-not-json}\n"
    )

    assert result.returncode == 0

    lines = [
        line
        for line in result.stdout.splitlines()
        if line.strip()
    ]

    assert len(lines) == 1

    response = decode_response(lines[0])

    assert response.status == "failed"

    error = response.payload["error"]

    assert error["code"] == "ANN_E_PROTOCOL_ERROR"
    assert "invalid JSON" in error["message"]

    assert "[ann-e-runtime-host]" in result.stderr


def test_host_ignores_blank_lines() -> None:
    request = RuntimeRequest(
        request_id=str(uuid4()),
        task_id=str(uuid4()),
        operation="health",
        payload={},
    )

    input_data = (
        "\n"
        "\n"
        + encode_message(request)
        + "\n"
        "\n"
    )

    result = _run_host_process(input_data)

    assert result.returncode == 0

    lines = [
        line
        for line in result.stdout.splitlines()
        if line.strip()
    ]

    assert len(lines) == 1

    response = decode_response(lines[0])

    assert response.request_id == request.request_id
    assert response.task_id == request.task_id
    assert response.status == "completed"


def test_host_exits_cleanly_on_empty_stdin() -> None:
    result = _run_host_process("")

    assert result.returncode == 0
    assert result.stdout == ""


def _run_host_process(
    input_data: str,
) -> subprocess.CompletedProcess[str]:
    runtime_source = (
        Path(__file__).resolve().parents[1] / "src"
    )

    environment = os.environ.copy()

    existing_pythonpath = environment.get("PYTHONPATH")

    if existing_pythonpath:
        environment["PYTHONPATH"] = (
            str(runtime_source)
            + os.pathsep
            + existing_pythonpath
        )
    else:
        environment["PYTHONPATH"] = str(runtime_source)

    return subprocess.run(
        [
            sys.executable,
            "-m",
            "anne_runtime.runtime_host",
        ],
        input=input_data,
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )

def test_host_streams_response_before_stdin_eof(monkeypatch) -> None:
    request = RuntimeRequest(
        request_id=str(uuid4()),
        task_id=str(uuid4()),
        operation="health",
        payload={},
    )

    encoded_request = encode_message(request) + "\n"

    response_written = threading.Event()
    allow_eof = threading.Event()
    output_lines: list[str] = []

    def fake_application(*, repository_root):
        return object()

    def fake_handle_line(*, raw_line, application):
        decoded_request = decode_request(raw_line)

        return RuntimeResponse(
            request_id=decoded_request.request_id,
            task_id=decoded_request.task_id,
            status="completed",
            payload={"healthy": True},
        )

    monkeypatch.setattr(
        "anne_runtime.runtime_host.RuntimeApplication",
        fake_application,
    )

    monkeypatch.setattr(
        "anne_runtime.runtime_host._handle_line",
        fake_handle_line,
    )

    class StreamingStdin:
        def __iter__(self):
            yield encoded_request

            assert response_written.wait(timeout=1.0), (
                "runtime host did not emit the response before stdin reached EOF"
            )

            allow_eof.wait(timeout=1.0)

    class StreamingStdout:
        def write(self, value):
            output_lines.append(value)
            if value.strip():
                response_written.set()
            return len(value)

        def flush(self):
            pass

    monkeypatch.setattr(
        "anne_runtime.runtime_host.sys",
        type(
            "FakeSys",
            (),
            {
                "stdin": StreamingStdin(),
                "stdout": StreamingStdout(),
            },
        ),
    )

    result_holder: list[int] = []

    def run():
        result_holder.append(run_host())

    host_thread = threading.Thread(target=run)
    host_thread.start()

    assert response_written.wait(timeout=1.0), (
        "runtime host did not produce a response while stdin remained open"
    )

    responses = [
        decode_response(line)
        for line in output_lines
        if line.strip()
    ]

    assert len(responses) == 1
    assert responses[0].request_id == request.request_id
    assert responses[0].task_id == request.task_id

    allow_eof.set()
    host_thread.join(timeout=1.0)

    assert not host_thread.is_alive()
    assert result_holder == [0]

def test_host_preserves_runtime_application_error_metadata(monkeypatch) -> None:
    request = RuntimeRequest(
        request_id=str(uuid4()),
        task_id=str(uuid4()),
        operation="message",
        payload={},
    )

    from anne_runtime.runtime_application import RuntimeApplicationError

    def failing_dispatch(*, request, application):
        raise RuntimeApplicationError(
            "model invocation failed: ModelProviderError",
            code="GEMINI_SERVER_ERROR",
            retryable=True,
        )

    monkeypatch.setattr(
        "anne_runtime.runtime_host._dispatch",
        failing_dispatch,
    )

    from anne_runtime.runtime_host import _handle_line

    response = _handle_line(
        raw_line=encode_message(request),
        application=object(),
    )

    assert response.request_id == request.request_id
    assert response.task_id == request.task_id
    assert response.status == "failed"

    error = response.payload["error"]

    assert error["code"] == "GEMINI_SERVER_ERROR"
    assert error["message"] == "model invocation failed: ModelProviderError"
    assert error["retryable"] is True
