from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID

from .runtime_application import (
    RuntimeApplication,
    RuntimeApplicationError,
)
from .runtime_protocol import (
    RuntimeProtocolError,
    RuntimeRequest,
    RuntimeResponse,
    decode_request,
    encode_message,
)


HOST_OPERATION = "host"


def run_host() -> int:
    """
    Run the Ann-E runtime host over newline-delimited JSON.

    stdin:
        One RuntimeRequest JSON object per line.

    stdout:
        One RuntimeResponse JSON object per request.

    stderr:
        Diagnostics only.
    """

    try:
        application = RuntimeApplication(
            repository_root=Path.cwd(),
        )
    except Exception as exc:
        _write_diagnostic(
            "Unable to initialize runtime application: "
            f"{type(exc).__name__}: {exc}"
        )
        return 1

    for raw_line in sys.stdin:
        line = raw_line.strip()

        if not line:
            continue

        response = _handle_line(
            raw_line=line,
            application=application,
        )

        try:
            sys.stdout.write(
                encode_message(response) + "\n"
            )
            sys.stdout.flush()
        except BrokenPipeError:
            return 0

    return 0


def _handle_line(
    *,
    raw_line: str,
    application: RuntimeApplication,
) -> RuntimeResponse:
    try:
        request = decode_request(raw_line)
    except RuntimeProtocolError as exc:
        request_id, task_id = _recover_identifiers(
            raw_line
        )

        _write_diagnostic(
            f"Rejected runtime request: {exc}"
        )

        return RuntimeResponse(
            request_id=request_id,
            task_id=task_id,
            status="failed",
            payload={
                "error": {
                    "code": "ANN_E_PROTOCOL_ERROR",
                    "message": str(exc),
                }
            },
        )

    try:
        return _dispatch(
            request=request,
            application=application,
        )
    except RuntimeApplicationError as exc:
        _write_diagnostic(
            "Runtime application rejected request: "
            f"{exc}"
        )

        return RuntimeResponse(
            request_id=request.request_id,
            task_id=request.task_id,
            status="failed",
            payload={
                "error": {
                    "code": "ANN_E_RUNTIME_APPLICATION_ERROR",
                    "message": str(exc),
                }
            },
        )
    except Exception as exc:
        _write_diagnostic(
            "Unhandled runtime host exception: "
            f"{type(exc).__name__}: {exc}"
        )

        return RuntimeResponse(
            request_id=request.request_id,
            task_id=request.task_id,
            status="failed",
            payload={
                "error": {
                    "code": "ANN_E_RUNTIME_HOST_ERROR",
                    "message": (
                        "The runtime host encountered an unexpected "
                        "internal error."
                    ),
                }
            },
        )


def _dispatch(
    request: RuntimeRequest,
    application: RuntimeApplication | None = None,
) -> RuntimeResponse:
    """
    Dispatch an already validated runtime request.

    The application dependency is optional for operations that do not
    require the application layer. This keeps the dispatch boundary
    directly testable while ensuring application-backed operations
    explicitly require the initialized RuntimeApplication.
    """

    if request.operation == "health":
        return RuntimeResponse(
            request_id=request.request_id,
            task_id=request.task_id,
            status="completed",
            payload={
                "healthy": True,
                "runtime_version": _runtime_version(),
                "host_operation": HOST_OPERATION,
            },
        )

    if request.operation == "message":
        if application is None:
            raise RuntimeApplicationError(
                "The runtime application is required for the "
                "'message' operation."
            )

        result = application.handle_message(
            request_id=request.request_id,
            task_id=request.task_id,
            payload=request.payload,
        )

        return RuntimeResponse(
            request_id=request.request_id,
            task_id=request.task_id,
            status="completed",
            payload=result,
        )

    return RuntimeResponse(
        request_id=request.request_id,
        task_id=request.task_id,
        status="failed",
        payload={
            "error": {
                "code": "ANN_E_UNSUPPORTED_OPERATION",
                "message": (
                    f"Unsupported runtime operation: "
                    f"{request.operation!r}"
                ),
            }
        },
    )


def _runtime_version() -> str:
    try:
        from . import __version__

        return str(__version__)
    except Exception:
        return "unknown"


def _recover_identifiers(
    raw_line: str,
) -> tuple[str, str]:
    request_id: str | None = None
    task_id: str | None = None

    try:
        decoded = json.loads(raw_line)

        if isinstance(decoded, Mapping):
            request_id = _valid_uuid_or_none(
                decoded.get("request_id")
            )
            task_id = _valid_uuid_or_none(
                decoded.get("task_id")
            )
    except Exception:
        pass

    if request_id is None:
        request_id = str(UUID(int=0))

    if task_id is None:
        task_id = str(UUID(int=0))

    return request_id, task_id


def _valid_uuid_or_none(
    value: Any,
) -> str | None:
    if not isinstance(value, str):
        return None

    try:
        parsed = UUID(value)
    except ValueError:
        return None

    return str(parsed)


def _write_diagnostic(
    message: str,
) -> None:
    print(
        f"[ann-e-runtime-host] {message}",
        file=sys.stderr,
        flush=True,
    )


if __name__ == "__main__":
    raise SystemExit(run_host())
