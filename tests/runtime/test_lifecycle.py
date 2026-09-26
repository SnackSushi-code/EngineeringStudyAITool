import unittest
from uuid import uuid4
from anne_runtime.contracts import TaskState
from anne_runtime.lifecycle import TaskLifecycle
from anne_runtime.errors import InvalidTransitionError

class LifecycleTests(unittest.TestCase):
    def test_events_are_ordered_and_correlated(self):
        rid, tid = uuid4(), uuid4()
        life = TaskLifecycle(rid, tid)
        life.transition(TaskState.PLANNING)
        life.transition(TaskState.RUNNING)
        events = life.events()
        self.assertEqual([1,2], [e.sequence for e in events])
        self.assertTrue(all(e.request_id == rid and e.task_id == tid for e in events))

    def test_invalid_transition_does_not_emit_event(self):
        life = TaskLifecycle(uuid4(), uuid4())
        with self.assertRaises(InvalidTransitionError):
            life.transition(TaskState.SUCCEEDED)
        self.assertEqual((), life.events())
