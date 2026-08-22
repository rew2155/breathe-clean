import unittest

from adapters.purifier import (
    PurifierCommand,
    PurifierControlError,
    PurifierControlResult,
    SimulatedPurifierAdapter,
)


class SimulatedPurifierAdapterTests(unittest.TestCase):
    def test_records_turn_on_command(self):
        adapter = SimulatedPurifierAdapter()

        result = adapter.set_state(purifier_id=123, desired_state=True)

        self.assertEqual(
            adapter.commands,
            [PurifierCommand(purifier_id=123, desired_state=True)],
        )
        self.assertEqual(result, PurifierControlResult(state_confirmed=True))

    def test_records_turn_off_command(self):
        adapter = SimulatedPurifierAdapter()

        adapter.set_state(purifier_id=123, desired_state=False)

        self.assertEqual(
            adapter.commands,
            [PurifierCommand(purifier_id=123, desired_state=False)],
        )

    def test_can_record_multiple_commands(self):
        adapter = SimulatedPurifierAdapter()

        adapter.set_state(purifier_id=123, desired_state=True)
        adapter.set_state(purifier_id=123, desired_state=False)

        self.assertEqual(len(adapter.commands), 2)

    def test_records_failed_command_and_raises_control_error(self):
        adapter = SimulatedPurifierAdapter(should_fail=True)

        with self.assertRaises(PurifierControlError):
            adapter.set_state(purifier_id=123, desired_state=True)

        self.assertEqual(
            adapter.commands,
            [PurifierCommand(purifier_id=123, desired_state=True)],
        )

    def test_rejects_invalid_purifier_id(self):
        adapter = SimulatedPurifierAdapter()

        with self.assertRaises(ValueError):
            adapter.set_state(purifier_id=0, desired_state=True)

        self.assertEqual(adapter.commands, [])

    def test_rejects_non_boolean_state(self):
        adapter = SimulatedPurifierAdapter()

        with self.assertRaises(TypeError):
            adapter.set_state(purifier_id=123, desired_state=1)

        self.assertEqual(adapter.commands, [])


if __name__ == "__main__":
    unittest.main()
