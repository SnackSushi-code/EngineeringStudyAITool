from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from anne_runtime.runtime_application import RuntimeApplication


def make_application(tmp_path: Path) -> RuntimeApplication:
    schema_dir = tmp_path / "packages" / "schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)

    return RuntimeApplication(
        repository_root=tmp_path,
    )


def test_runtime_application_creates_session_database(tmp_path: Path) -> None:
    application = make_application(tmp_path)

    database_path = (
        tmp_path
        / "runtime-data"
        / "conversation_sessions.sqlite3"
    )

    assert database_path.is_file()

    session_id = application.create_session()
    assert session_id


def test_runtime_application_session_survives_new_application(
    tmp_path: Path,
) -> None:
    application_one = make_application(tmp_path)

    session_id = application_one.create_session()

    application_one._conversation_sessions.append_message(
        __import__("uuid").UUID(session_id),
        {
            "role": "user",
            "content": "Persist this runtime session.",
        },
    )

    application_two = make_application(tmp_path)

    parsed_session_id = __import__("uuid").UUID(session_id)

    assert application_two._conversation_sessions.has_session(
        parsed_session_id
    )

    assert application_two._conversation_sessions.get_conversation(
        parsed_session_id
    ) == (
        {
            "role": "user",
            "content": "Persist this runtime session.",
        },
    )


def test_runtime_application_clear_persists_across_instances(
    tmp_path: Path,
) -> None:
    application_one = make_application(tmp_path)

    session_id = application_one.create_session()
    parsed_session_id = __import__("uuid").UUID(session_id)

    application_one._conversation_sessions.append_message(
        parsed_session_id,
        {
            "role": "user",
            "content": "This should be cleared.",
        },
    )

    application_one.clear_session(session_id)

    application_two = make_application(tmp_path)

    assert application_two._conversation_sessions.has_session(
        parsed_session_id
    )

    assert application_two._conversation_sessions.get_conversation(
        parsed_session_id
    ) == ()


def test_runtime_application_delete_persists_across_instances(
    tmp_path: Path,
) -> None:
    application_one = make_application(tmp_path)

    session_id = application_one.create_session()
    parsed_session_id = __import__("uuid").UUID(session_id)

    application_one._conversation_sessions.append_message(
        parsed_session_id,
        {
            "role": "user",
            "content": "This should be deleted.",
        },
    )

    application_one.delete_session(session_id)

    application_two = make_application(tmp_path)

    assert not application_two._conversation_sessions.has_session(
        parsed_session_id
    )

def test_runtime_application_session_recovers_across_processes(
    tmp_path: Path,
) -> None:
    schema_dir = tmp_path / "packages" / "schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)

    runtime_source = Path(__file__).resolve().parents[1] / "src"

    environment = os.environ.copy()
    existing_pythonpath = environment.get("PYTHONPATH")

    environment["PYTHONPATH"] = (
        str(runtime_source)
        if not existing_pythonpath
        else os.pathsep.join(
            (str(runtime_source), existing_pythonpath)
        )
    )

    writer_code = """
import sys
from pathlib import Path
from uuid import UUID

from anne_runtime.runtime_application import RuntimeApplication

repository_root = Path(sys.argv[1])

application = RuntimeApplication(
    repository_root=repository_root,
)

session_id = application.create_session()
parsed_session_id = UUID(session_id)

application._conversation_sessions.append_message(
    parsed_session_id,
    {
        "role": "user",
        "content": "Recover this runtime conversation across processes.",
    },
)

application._conversation_sessions.append_message(
    parsed_session_id,
    {
        "role": "assistant",
        "content": "The conversation was persisted by Process A.",
    },
)

print(session_id)
"""

    writer = subprocess.run(
        [
            sys.executable,
            "-c",
            writer_code,
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert writer.returncode == 0, writer.stderr

    session_id = writer.stdout.strip()

    assert session_id

    reader_code = """
import json
import sys
from pathlib import Path
from uuid import UUID

from anne_runtime.runtime_application import RuntimeApplication

repository_root = Path(sys.argv[1])
session_id = sys.argv[2]

application = RuntimeApplication(
    repository_root=repository_root,
)

parsed_session_id = UUID(session_id)

assert application._conversation_sessions.has_session(
    parsed_session_id
)

conversation = application._conversation_sessions.get_conversation(
    parsed_session_id
)

print(json.dumps(list(conversation)))
"""

    reader = subprocess.run(
        [
            sys.executable,
            "-c",
            reader_code,
            str(tmp_path),
            session_id,
        ],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert reader.returncode == 0, reader.stderr

    recovered_conversation = json.loads(reader.stdout)

    assert recovered_conversation == [
        {
            "role": "user",
            "content": "Recover this runtime conversation across processes.",
        },
        {
            "role": "assistant",
            "content": "The conversation was persisted by Process A.",
        },
    ]
