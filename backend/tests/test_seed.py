import unittest

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from database import Base
from models import Room
from seed import DEMO_ROOM_NAMES, seed_demo_rooms


class SeedDemoRoomsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, expire_on_commit=False)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_creates_four_rooms_with_one_sensor_and_purifier_each(self):
        rooms = seed_demo_rooms(self.db)

        self.assertEqual({room.name for room in rooms}, set(DEMO_ROOM_NAMES))
        self.assertTrue(all(room.sensor is not None for room in rooms))
        self.assertTrue(all(room.purifier is not None for room in rooms))

    def test_is_idempotent(self):
        seed_demo_rooms(self.db)
        seed_demo_rooms(self.db)

        count = self.db.scalar(select(func.count()).select_from(Room))
        self.assertEqual(count, 4)

    def test_renames_legacy_room_without_losing_its_identity(self):
        legacy = Room(name="Legacy Room")
        self.db.add(legacy)
        self.db.commit()
        legacy_id = legacy.id

        seed_demo_rooms(self.db)

        master_bedroom = self.db.scalar(
            select(Room).where(Room.name == "Master Bedroom")
        )
        self.assertEqual(master_bedroom.id, legacy_id)


if __name__ == "__main__":
    unittest.main()
