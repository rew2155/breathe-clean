import unittest
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import ValidationError

from messaging.messages import (
    PurifierCommandMessage,
    PurifierStateMessage,
    SensorReadingMessage,
)
from messaging.topics import (
    purifier_commands_topic,
    purifier_id_from_state_topic,
    purifier_state_topic,
    sensor_id_from_readings_topic,
    sensor_readings_topic,
)


class MqttTopicTests(unittest.TestCase):
    def test_builds_versioned_device_topics(self):
        self.assertEqual(
            sensor_readings_topic(123),
            "breathe-clean/v1/sensors/123/readings",
        )
        self.assertEqual(
            purifier_commands_topic(456),
            "breathe-clean/v1/purifiers/456/commands",
        )
        self.assertEqual(
            purifier_state_topic(456),
            "breathe-clean/v1/purifiers/456/state",
        )

    def test_builds_subscription_topics(self):
        self.assertEqual(
            sensor_readings_topic(),
            "breathe-clean/v1/sensors/+/readings",
        )
        self.assertEqual(
            purifier_state_topic(),
            "breathe-clean/v1/purifiers/+/state",
        )

    def test_rejects_invalid_device_id(self):
        with self.assertRaises(ValueError):
            sensor_readings_topic(0)
        with self.assertRaises(TypeError):
            sensor_readings_topic("123")

    def test_extracts_purifier_id_from_state_topic(self):
        self.assertEqual(
            purifier_id_from_state_topic(
                "breathe-clean/v1/purifiers/456/state"
            ),
            456,
        )

    def test_extracts_sensor_id_from_readings_topic(self):
        self.assertEqual(
            sensor_id_from_readings_topic(
                "breathe-clean/v1/sensors/123/readings"
            ),
            123,
        )

    def test_rejects_invalid_purifier_state_topic(self):
        with self.assertRaises(ValueError):
            purifier_id_from_state_topic(
                "breathe-clean/v2/purifiers/456/state"
            )


class MqttMessageTests(unittest.TestCase):
    now = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)

    def test_serializes_sensor_reading_as_json(self):
        message_id = uuid4()
        message = SensorReadingMessage(
            message_id=message_id,
            sensor_id=123,
            pm25=12.5,
            recorded_at=self.now,
        )

        payload = message.model_dump_json()
        decoded = SensorReadingMessage.model_validate_json(payload)

        self.assertEqual(decoded, message)

    def test_rejects_invalid_sensor_reading(self):
        with self.assertRaises(ValidationError):
            SensorReadingMessage(
                message_id=uuid4(),
                sensor_id=123,
                pm25=float("nan"),
                recorded_at=self.now,
            )

    def test_rejects_unknown_message_fields(self):
        with self.assertRaises(ValidationError):
            PurifierCommandMessage(
                message_id=uuid4(),
                purifier_id=456,
                desired_state=True,
                issued_at=self.now,
                unexpected="value",
            )

    def test_links_reported_state_to_command(self):
        command_id = uuid4()
        state = PurifierStateMessage(
            message_id=uuid4(),
            command_id=command_id,
            purifier_id=456,
            is_on=True,
            observed_at=self.now,
        )

        self.assertEqual(state.command_id, command_id)

    def test_requires_timezone_aware_timestamps(self):
        with self.assertRaises(ValidationError):
            SensorReadingMessage(
                message_id=uuid4(),
                sensor_id=123,
                pm25=12.5,
                recorded_at=datetime(2026, 8, 22, 12, 0),
            )


if __name__ == "__main__":
    unittest.main()
