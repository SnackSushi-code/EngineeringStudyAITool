import unittest

from anne_runtime.contracts import TaskState
from anne_runtime.errors import InvalidTransitionError
from anne_runtime.state_machine import TaskStateMachine


class TaskStateMachineTests(unittest.TestCase):
    def test_normal_lifecycle(self):
        machine = TaskStateMachine()
        for state in (
            TaskState.PLANNING,
            TaskState.WAITING_APPROVAL,
            TaskState.RUNNING,
            TaskState.VALIDATING,
            TaskState.SUCCEEDED,
        ):
            machine.transition(state)

        self.assertEqual(TaskState.SUCCEEDED, machine.state)

    def test_terminal_state_cannot_reactivate(self):
        machine = TaskStateMachine(TaskState.SUCCEEDED)
        with self.assertRaises(InvalidTransitionError):
            machine.transition(TaskState.RUNNING)

    def test_invalid_transition_rejected(self):
        machine = TaskStateMachine(TaskState.QUEUED)
        with self.assertRaises(InvalidTransitionError):
            machine.transition(TaskState.SUCCEEDED)
