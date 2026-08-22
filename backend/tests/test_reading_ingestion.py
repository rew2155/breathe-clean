import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from adapters.purifier import (
    PurifierControlError,
    SimulatedPurifierAdapter,
)
from database import Base
from main import create_reading, create_room
from models import Purifier, SensorReading
from schemas import RoomCreate, SensorReadingCreate
from services.air_quality import EvaluationStatus


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

    def test_evaluates_after_three_recent_readings(self):
        first = self.ingest(20)
        second = self.ingest(20)
        third = self.ingest(20)

        self.assertEqual(
            first.evaluation.status,
            EvaluationStatus.INSUFFICIENT_DATA,
        )
        self.assertEqual(
            second.evaluation.status,
            EvaluationStatus.INSUFFICIENT_DATA,
        )
        self.assertEqual(third.evaluation.status, EvaluationStatus.READY)
        self.assertEqual(third.evaluation.average_pm25, 20)
        self.assertTrue(third.evaluation.desired_purifier_state)

        purifier = self.db.get(Purifier, self.room.purifier.id)
        self.assertTrue(purifier.is_on)
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
        self.ingest(20)
        self.ingest(20)

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
        self.assertEqual(len(failing_adapter.commands), 1)
        self.assertEqual(
            self.db.scalar(select(func.count()).select_from(SensorReading)),
            2,
        )


if __name__ == "__main__":
    unittest.main()
