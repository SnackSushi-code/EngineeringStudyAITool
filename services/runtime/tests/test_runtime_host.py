from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from anne_runtime.runtime_host import _dispatch
from anne_runtime.runtime_protocol import (
    RuntimeRequest,
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

    assert responses[0].request_id == requests[0].request_id
    assert responses[0].status == "completed"

    assert responses[1].request_id == requests[1].request_id
    assert responses[1].status == "completed"

    assert responses[2].request_id == requests[2].request_id
    assert responses[2].status == "failed"


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
