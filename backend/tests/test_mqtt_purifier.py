import unittest
from datetime import datetime, timezone
from uuid import uuid4

from adapters.mqtt_purifier import MqttPurifierAdapter
from adapters.purifier import PurifierControlError
from messaging.messages import PurifierCommandMessage
from messaging.transport import MqttTransportError


class FakeTransport:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.published = []

    def publish(self, topic, message):
        if self.should_fail:
            raise MqttTransportError("broker unavailable")
        self.published.append((topic, message))

    def subscribe(self, topic, handler):
        pass


class MqttPurifierAdapterTests(unittest.TestCase):
    def test_publishes_command_and_returns_pending_result(self):
        transport = FakeTransport()
        command_id = uuid4()
        issued_at = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
        adapter = MqttPurifierAdapter(
            transport,
            id_factory=lambda: command_id,
            clock=lambda: issued_at,
        )

        result = adapter.set_state(123, True)

        topic, message = transport.published[0]
        self.assertEqual(topic, "breathe-clean/v1/purifiers/123/commands")
        self.assertEqual(
            message,
            PurifierCommandMessage(
                message_id=command_id,
                purifier_id=123,
                desired_state=True,
                issued_at=issued_at,
            ),
        )
        self.assertFalse(result.state_confirmed)
        self.assertEqual(result.command_id, command_id)

    def test_translates_transport_failure(self):
        adapter = MqttPurifierAdapter(FakeTransport(should_fail=True))

        with self.assertRaises(PurifierControlError):
            adapter.set_state(123, True)


if __name__ == "__main__":
    unittest.main()
