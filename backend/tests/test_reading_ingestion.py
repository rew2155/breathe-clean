import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from adapters.purifier import (
    PurifierCommand,
    PurifierControlError,
    PurifierControlResult,
    SimulatedPurifierAdapter,
)
from database import Base
from main import create_reading, create_room
from models import Purifier, SensorReading
from schemas import RoomCreate, SensorReadingCreate
from services.air_quality import EvaluationStatus


class PendingPurifierAdapter:
    def __init__(self):
        self.commands = []

    def set_state(self, purifier_id: int, desired_state: bool):
        self.commands.append(PurifierCommand(purifier_id, desired_state))
        return PurifierControlResult(state_confirmed=False)


class ReadingIngestionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, expire_on_commit=False)
        self.room = create_room(RoomCreate(name="Office"), self.db)
        self.adapter = SimulatedPurifierAdapter()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def ingest(self, pm25: float):
        return create_reading(
            SensorReadingCreate(
                pm25=pm25,
                sensor_id=self.room.sensor.id,
            ),
            self.db,
            self.adapter,
        )

    def test_evaluates_after_first_recent_reading(self):
        first = self.ingest(20)
        second = self.ingest(20)
        third = self.ingest(20)

        self.assertEqual(first.evaluation.status, EvaluationStatus.READY)
        self.assertEqual(second.evaluation.status, EvaluationStatus.READY)
        self.assertEqual(third.evaluation.status, EvaluationStatus.READY)
        self.assertEqual(third.evaluation.average_pm25, 20)
        self.assertTrue(third.evaluation.desired_purifier_state)

        purifier = self.db.get(Purifier, self.room.purifier.id)
        self.assertTrue(purifier.is_on)
        self.assertTrue(purifier.desired_is_on)
        self.assertEqual(len(self.adapter.commands), 1)
        self.assertEqual(
            self.db.scalar(select(func.count()).select_from(SensorReading)),
            3,
        )

    def test_rejects_unknown_sensor_without_storing_reading(self):
        with self.assertRaises(HTTPException) as context:
            create_reading(
                SensorReadingCreate(pm25=10, sensor_id=999),
                self.db,
                self.adapter,
            )

        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(
            self.db.scalar(select(func.count()).select_from(SensorReading)),
            0,
        )

    def test_does_not_repeat_command_when_state_already_matches(self):
        self.ingest(20)
        self.ingest(20)
        self.ingest(20)
        self.ingest(20)

        self.assertEqual(len(self.adapter.commands), 1)

    def test_does_not_update_state_when_adapter_fails(self):
        failing_adapter = SimulatedPurifierAdapter(should_fail=True)

        with self.assertRaises(PurifierControlError):
            create_reading(
                SensorReadingCreate(
                    pm25=20,
                    sensor_id=self.room.sensor.id,
                ),
                self.db,
                failing_adapter,
            )
        self.db.rollback()

        purifier = self.db.get(Purifier, self.room.purifier.id)
        self.assertFalse(purifier.is_on)
        self.assertFalse(purifier.desired_is_on)
        self.assertEqual(len(failing_adapter.commands), 1)
        self.assertEqual(
            self.db.scalar(select(func.count()).select_from(SensorReading)),
            0,
        )

    def test_tracks_requested_state_until_device_confirms_it(self):
        pending_adapter = PendingPurifierAdapter()
        create_reading(
            SensorReadingCreate(
                pm25=20,
                sensor_id=self.room.sensor.id,
            ),
            self.db,
            pending_adapter,
        )

        purifier = self.db.get(Purifier, self.room.purifier.id)
        self.assertTrue(purifier.desired_is_on)
        self.assertFalse(purifier.is_on)
        self.assertEqual(len(pending_adapter.commands), 1)


if __name__ == "__main__":
    unittest.main()
