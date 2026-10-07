from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from anne_runtime.runtime_application import RuntimeApplication


def make_application(tmp_path: Path) -> RuntimeApplication:
    schema_dir = tmp_path / "packages" / "schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)
    return RuntimeApplication(repository_root=tmp_path)


def test_runtime_context_bounds_explicit_conversation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    application = make_application(tmp_path)
    captured = []

    def fake_run(intelligence_request, task_request):
        captured.append(intelligence_request)
        return type(
            "Outcome",
            (),
            {
                "final_response": "bounded",
                "completed": True,
                "iterations": (
                    type(
                        "Iteration",
                        (),
                        {
                            "invocation": type(
                                "Invocation",
                                (),
                                {
                                    "provider_id": "test",
                                    "provider_version": "1.0",
                                    "model": "test",
                                },
                            )(),
                        },
                    )(),
                ),
                "stop_reason": "FINAL_RESPONSE",
            },
        )()

    monkeypatch.setattr(application._planning_loop, "run", fake_run)

    conversation = tuple(
        {
            "role": "user" if index % 2 == 0 else "assistant",
            "content": f"message-{index}",
        }
        for index in range(40)
    )

    application.handle_message(
        request_id=str(uuid4()),
        task_id=str(uuid4()),
        payload={
            "user_intent": "Current question",
            "conversation": list(conversation),
        },
    )

    assert len(captured) == 1

    bounded = captured[0].conversation

    assert len(bounded) <= 32
    assert bounded == conversation[-32:]
    assert captured[0].user_intent == "Current question"


def test_runtime_context_preserves_tool_messages(
    tmp_path: Path,
    monkeypatch,
) -> None:
    application = make_application(tmp_path)
    captured = []

    def fake_run(intelligence_request, task_request):
        captured.append(intelligence_request)
        return type(
            "Outcome",
            (),
            {
                "final_response": "bounded",
                "completed": True,
                "iterations": (SimpleNamespace(invocation=SimpleNamespace(provider_id="test", provider_version="1.0", model="test")),), "stop_reason": "FINAL_RESPONSE",
            },
        )()

    monkeypatch.setattr(application._planning_loop, "run", fake_run)

    conversation = [
        {"role": "user", "content": "Earlier question"},
        {"role": "assistant", "content": "Earlier answer"},
        {
            "role": "assistant",
            "content": '{"decision_type":"TOOL_PROPOSAL","tool":"anne.calculator"}',
        },
        {
            "role": "tool",
            "name": "anne.calculator",
            "content": '{"result": 42}',
        },
    ]

    application.handle_message(
        request_id=str(uuid4()),
        task_id=str(uuid4()),
        payload={
            "user_intent": "Use the previous calculation.",
            "conversation": conversation,
        },
    )

    bounded = captured[0].conversation

    assert bounded[-1]["role"] == "tool"
    assert bounded[-1]["name"] == "anne.calculator"


def test_runtime_context_keeps_current_user_intent_separate_from_history(
    tmp_path: Path,
    monkeypatch,
) -> None:
    application = make_application(tmp_path)
    captured = []

    def fake_run(intelligence_request, task_request):
        captured.append(intelligence_request)
        return type(
            "Outcome",
            (),
            {
                "final_response": "ok",
                "completed": True,
                "iterations": (SimpleNamespace(invocation=SimpleNamespace(provider_id="test", provider_version="1.0", model="test")),), "stop_reason": "FINAL_RESPONSE",
            },
        )()

    monkeypatch.setattr(application._planning_loop, "run", fake_run)

    session_id = application.create_session()

    application.handle_message(
        request_id=str(uuid4()),
        task_id=str(uuid4()),
        payload={
            "session_id": session_id,
            "user_intent": "Current session question",
        },
    )

    request = captured[0]

    assert request.user_intent == "Current session question"

    matching_user_messages = [
        message
        for message in request.conversation
        if message["role"] == "user"
        and message["content"] == "Current session question"
    ]

    assert matching_user_messages == []


def test_runtime_context_preserves_persisted_session_history(
    tmp_path: Path,
    monkeypatch,
) -> None:
    application = make_application(tmp_path)
    session_id = application.create_session()

    application._conversation_sessions.append_message(
        __import__("uuid").UUID(session_id),
        {"role": "user", "content": "Old question"},
    )
    application._conversation_sessions.append_message(
        __import__("uuid").UUID(session_id),
        {"role": "assistant", "content": "Old answer"},
    )

    captured = []

    def fake_run(intelligence_request, task_request):
        captured.append(intelligence_request)
        return type(
            "Outcome",
            (),
            {
                "final_response": "ok",
                "completed": True,
                "iterations": (SimpleNamespace(invocation=SimpleNamespace(provider_id="test", provider_version="1.0", model="test")),), "stop_reason": "FINAL_RESPONSE",
            },
        )()

    monkeypatch.setattr(application._planning_loop, "run", fake_run)

    application.handle_message(
        request_id=str(uuid4()),
        task_id=str(uuid4()),
        payload={
            "session_id": session_id,
            "user_intent": "New question",
        },
    )

    conversation = captured[0].conversation

    assert conversation == (
        {"role": "user", "content": "Old question"},
        {"role": "assistant", "content": "Old answer"},
    )


def test_runtime_context_keeps_current_intent_when_history_is_truncated(
    tmp_path: Path,
    monkeypatch,
) -> None:
    application = make_application(tmp_path)
    captured = []

    def fake_run(intelligence_request, task_request):
        captured.append(intelligence_request)
        return type(
            "Outcome",
            (),
            {
                "final_response": "ok",
                "completed": True,
                "iterations": (SimpleNamespace(invocation=SimpleNamespace(provider_id="test", provider_version="1.0", model="test")),), "stop_reason": "FINAL_RESPONSE",
            },
        )()

    monkeypatch.setattr(application._planning_loop, "run", fake_run)

    conversation = [
        {
            "role": "user",
            "content": f"old-{index}",
        }
        for index in range(40)
    ]

    application.handle_message(
        request_id=str(uuid4()),
        task_id=str(uuid4()),
        payload={
            "user_intent": "Important current question",
            "conversation": conversation,
        },
    )

    request = captured[0]

    assert request.user_intent == "Important current question"
    assert len(request.conversation) <= 32



def test_runtime_context_recovers_and_bounds_history_across_processes(
    tmp_path: Path,
) -> None:
    schema_dir = tmp_path / "packages" / "schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)

    runtime_source = Path(__file__).resolve().parents[1] / "src"

    environment = __import__("os").environ.copy()
    existing_pythonpath = environment.get("PYTHONPATH")

    environment["PYTHONPATH"] = (
        str(runtime_source)
        if not existing_pythonpath
        else __import__("os").pathsep.join(
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

for index in range(40):
    application._conversation_sessions.append_message(
        parsed_session_id,
        {
            "role": "user" if index % 2 == 0 else "assistant",
            "content": f"persisted-message-{index}",
        },
    )

print(session_id)
"""

    writer = __import__("subprocess").run(
        [
            __import__("sys").executable,
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
from types import SimpleNamespace

from anne_runtime.runtime_application import RuntimeApplication

repository_root = Path(sys.argv[1])
session_id = sys.argv[2]

application = RuntimeApplication(
    repository_root=repository_root,
)

captured = []


def fake_run(intelligence_request, task_request):
    captured.append(intelligence_request)
    return SimpleNamespace(
        final_response="ok",
        completed=True,
        iterations=(
            SimpleNamespace(
                invocation=SimpleNamespace(
                    provider_id="test",
                    provider_version="1.0",
                    model="test",
                )
            ),
        ),
        stop_reason="FINAL_RESPONSE",
    )


application._planning_loop.run = fake_run

application.handle_message(
    request_id="00000000-0000-0000-0000-000000000101",
    task_id="00000000-0000-0000-0000-000000000102",
    payload={
        "session_id": session_id,
        "user_intent": "Important recovered current question",
    },
)

assert len(captured) == 1

request = captured[0]

print(
    json.dumps(
        {
            "user_intent": request.user_intent,
            "conversation": list(request.conversation),
        }
    )
)
"""

    reader = __import__("subprocess").run(
        [
            __import__("sys").executable,
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

    result = __import__("json").loads(reader.stdout)

    assert result["user_intent"] == "Important recovered current question"

    conversation = result["conversation"]

    assert len(conversation) == 32

    assert conversation == [
        {
            "role": "user" if index % 2 == 0 else "assistant",
            "content": f"persisted-message-{index}",
        }
        for index in range(8, 40)
    ]

    assert all(
        message["content"] != "Important recovered current question"
        for message in conversation
    )

