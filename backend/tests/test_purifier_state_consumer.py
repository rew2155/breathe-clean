import unittest
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from messaging.consumers import MessageProcessingStatus, PurifierStateConsumer
from messaging.messages import PurifierStateMessage
from models import Purifier, Room


class FakeTransport:
    def __init__(self):
        self.subscriptions = []

    def publish(self, topic, message):
        pass

    def subscribe(self, topic, handler):
        self.subscriptions.append((topic, handler))


class PurifierStateConsumerTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.SessionFactory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )
        self.command_id = uuid4()
        with self.SessionFactory() as db:
            room = Room(name="Office")
            room.purifier = Purifier(
                is_on=False,
                desired_is_on=True,
                pending_command_id=self.command_id,
            )
            db.add(room)
            db.commit()
            self.purifier_id = room.purifier.id

        self.transport = FakeTransport()
        self.consumer = PurifierStateConsumer(
            self.transport,
            self.SessionFactory,
        )

    def tearDown(self):
        self.engine.dispose()

    def payload(
        self,
        *,
        purifier_id=None,
        command_id=None,
        is_on=True,
    ):
        return PurifierStateMessage(
            message_id=uuid4(),
            command_id=command_id or self.command_id,
            purifier_id=purifier_id or self.purifier_id,
            is_on=is_on,
            observed_at=datetime.now(timezone.utc),
        ).model_dump_json().encode()

    def test_subscribes_to_all_purifier_states(self):
        self.consumer.start()

        self.assertEqual(
            self.transport.subscriptions[0][0],
            "breathe-clean/v1/purifiers/+/state",
        )

    def test_confirms_matching_pending_command(self):
        status = self.consumer.handle_message(
            f"breathe-clean/v1/purifiers/{self.purifier_id}/state",
            self.payload(),
        )

        self.assertEqual(status, MessageProcessingStatus.PROCESSED)
        with self.SessionFactory() as db:
            purifier = db.get(Purifier, self.purifier_id)
            self.assertTrue(purifier.is_on)
            self.assertTrue(purifier.desired_is_on)
            self.assertIsNone(purifier.pending_command_id)

    def test_ignores_acknowledgment_for_old_command(self):
        status = self.consumer.handle_message(
            f"breathe-clean/v1/purifiers/{self.purifier_id}/state",
            self.payload(command_id=uuid4()),
        )

        self.assertEqual(status, MessageProcessingStatus.IGNORED)
        with self.SessionFactory() as db:
            purifier = db.get(Purifier, self.purifier_id)
            self.assertFalse(purifier.is_on)
            self.assertEqual(purifier.pending_command_id, self.command_id)

    def test_rejects_topic_payload_id_mismatch(self):
        status = self.consumer.handle_message(
            f"breathe-clean/v1/purifiers/{self.purifier_id}/state",
            self.payload(purifier_id=self.purifier_id + 1),
        )

        self.assertEqual(status, MessageProcessingStatus.REJECTED)

    def test_resets_desired_state_when_device_did_not_apply_command(self):
        status = self.consumer.handle_message(
            f"breathe-clean/v1/purifiers/{self.purifier_id}/state",
            self.payload(is_on=False),
        )

        self.assertEqual(status, MessageProcessingStatus.PROCESSED)
        with self.SessionFactory() as db:
            purifier = db.get(Purifier, self.purifier_id)
            self.assertFalse(purifier.is_on)
            self.assertFalse(purifier.desired_is_on)
            self.assertIsNone(purifier.pending_command_id)


if __name__ == "__main__":
    unittest.main()
