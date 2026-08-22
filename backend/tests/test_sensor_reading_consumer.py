import unittest
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from adapters.purifier import SimulatedPurifierAdapter
from database import Base
from messaging.consumers import MessageProcessingStatus, SensorReadingConsumer
from messaging.messages import SensorReadingMessage
from messaging.transport import MessageDisposition
from models import Purifier, Room, Sensor, SensorReading


class FakeTransport:
    def __init__(self):
        self.subscriptions = []

    def publish(self, topic, message):
        pass

    def subscribe(self, topic, handler):
        self.subscriptions.append((topic, handler))


class SensorReadingConsumerTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.SessionFactory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )
        with self.SessionFactory() as db:
            room = Room(
                name="Office",
                sensor=Sensor(),
                purifier=Purifier(),
            )
            db.add(room)
            db.commit()
            self.sensor_id = room.sensor.id
            self.purifier_id = room.purifier.id

        self.transport = FakeTransport()
        self.adapter = SimulatedPurifierAdapter()
        self.consumer = SensorReadingConsumer(
            self.transport,
            self.SessionFactory,
            self.adapter,
        )

    def tearDown(self):
        self.engine.dispose()

    def payload(self, *, message_id=None, sensor_id=None, pm25=20):
        return SensorReadingMessage(
            message_id=message_id or uuid4(),
            sensor_id=sensor_id or self.sensor_id,
            pm25=pm25,
            recorded_at=datetime.now(timezone.utc),
        ).model_dump_json().encode()

    def handle(self, payload):
        return self.consumer.handle_message(
            f"breathe-clean/v1/sensors/{self.sensor_id}/readings",
            payload,
        )

    def test_subscribes_to_all_sensor_readings(self):
        self.consumer.start()

        self.assertEqual(
            self.transport.subscriptions[0][0],
            "breathe-clean/v1/sensors/+/readings",
        )

    def test_requests_acknowledgment_after_success(self):
        self.consumer.start()
        _, handler = self.transport.subscriptions[0]

        disposition = handler(
            f"breathe-clean/v1/sensors/{self.sensor_id}/readings",
            self.payload(),
        )

        self.assertEqual(disposition, MessageDisposition.ACKNOWLEDGE)

    def test_ingests_messages_and_runs_purifier_policy(self):
        statuses = [self.handle(self.payload()) for _ in range(3)]

        self.assertEqual(
            statuses,
            [MessageProcessingStatus.PROCESSED] * 3,
        )
        with self.SessionFactory() as db:
            purifier = db.get(Purifier, self.purifier_id)
            self.assertTrue(purifier.is_on)
            self.assertEqual(
                db.scalar(select(func.count()).select_from(SensorReading)),
                3,
            )
        self.assertEqual(len(self.adapter.commands), 1)

    def test_ignores_duplicate_message(self):
        message_id = uuid4()
        payload = self.payload(message_id=message_id)

        first = self.handle(payload)
        duplicate = self.handle(payload)

        self.assertEqual(first, MessageProcessingStatus.PROCESSED)
        self.assertEqual(duplicate, MessageProcessingStatus.IGNORED)
        with self.SessionFactory() as db:
            self.assertEqual(
                db.scalar(select(func.count()).select_from(SensorReading)),
                1,
            )

    def test_rejects_topic_payload_sensor_mismatch(self):
        status = self.handle(self.payload(sensor_id=self.sensor_id + 1))

        self.assertEqual(status, MessageProcessingStatus.REJECTED)

    def test_rejects_malformed_json(self):
        status = self.handle(b"not-json")

        self.assertEqual(status, MessageProcessingStatus.REJECTED)


if __name__ == "__main__":
    unittest.main()
