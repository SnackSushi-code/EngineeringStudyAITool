import unittest
from uuid import uuid4

from anne_runtime.observability import InMemoryEventSink, RuntimeTelemetry


class ObservabilityTests(unittest.TestCase):
    def test_event_is_correlated_and_redacted(self):
        sink = InMemoryEventSink()
        telemetry = RuntimeTelemetry(sink)
        event = telemetry.emit(
            "runtime.task.started",
            request_id=uuid4(),
            task_id=uuid4(),
            fields={"token": "SECRET", "safe": "value"},
        )
        payload = event.to_dict()
        self.assertNotEqual("SECRET", payload["fields"]["token"])
        self.assertEqual("value", payload["fields"]["safe"])

    def test_sink_preserves_order(self):
        sink = InMemoryEventSink()
        telemetry = RuntimeTelemetry(sink)
        telemetry.emit("one")
        telemetry.emit("two")
        self.assertEqual(("one", "two"), tuple(e.name for e in sink.events()))
