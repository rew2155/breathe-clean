import unittest
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database import Base
from main import create_room, get_room, get_room_readings
from models import SensorReading
from schemas import RoomCreate, RoomResponse, SensorReadingResponse


class RoomHistoryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, expire_on_commit=False)
        self.room = create_room(RoomCreate(name="Office"), self.db)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_returns_only_room_readings_newest_first(self):
        now = datetime.now(timezone.utc)
        older = SensorReading(
            sensor_id=self.room.sensor.id,
            pm25=8,
            created_at=now - timedelta(minutes=4),
        )
        newer = SensorReading(
            sensor_id=self.room.sensor.id,
            pm25=18,
            created_at=now,
        )
        other_room = create_room(RoomCreate(name="Kitchen"), self.db)
        other = SensorReading(sensor_id=other_room.sensor.id, pm25=30)
        self.db.add_all([older, newer, other])
        self.db.commit()

        readings = get_room_readings(self.room.id, self.db)

        self.assertEqual([reading.id for reading in readings], [newer.id, older.id])

    def test_missing_room_returns_not_found(self):
        for endpoint in (get_room, get_room_readings):
            with self.subTest(endpoint=endpoint.__name__):
                with self.assertRaises(HTTPException) as context:
                    endpoint(999, self.db)
                self.assertEqual(context.exception.status_code, 404)

    def test_serializes_large_ids_as_strings_for_javascript(self):
        room_json = RoomResponse.model_validate(self.room).model_dump(mode="json")
        reading = SensorReading(sensor_id=self.room.sensor.id, pm25=10)
        self.db.add(reading)
        self.db.commit()
        reading_json = SensorReadingResponse.model_validate(reading).model_dump(
            mode="json"
        )

        self.assertIsInstance(room_json["id"], str)
        self.assertIsInstance(room_json["sensor"]["id"], str)
        self.assertIsInstance(reading_json["sensor_id"], str)


if __name__ == "__main__":
    unittest.main()
