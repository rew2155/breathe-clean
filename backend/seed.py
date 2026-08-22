from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from database import SessionLocal
from models import Purifier, Room, Sensor


DEMO_ROOM_NAMES = (
    "Master Bedroom",
    "Living Room",
    "Kitchen",
    "Home Office",
)


def seed_demo_rooms(db: Session) -> list[Room]:
    """Create the four demo rooms and their devices without duplicating data."""
    existing_rooms = {
        room.name.casefold(): room
        for room in db.scalars(select(Room)).all()
    }

    legacy_room = existing_rooms.get("legacy room")
    if legacy_room and "master bedroom" not in existing_rooms:
        legacy_room.name = "Master Bedroom"
        existing_rooms["master bedroom"] = legacy_room

    for name in DEMO_ROOM_NAMES:
        room = existing_rooms.get(name.casefold())
        if room is None:
            room = Room(name=name, sensor=Sensor(), purifier=Purifier())
            db.add(room)
            existing_rooms[name.casefold()] = room
            continue

        if room.sensor is None:
            room.sensor = Sensor()
        if room.purifier is None:
            room.purifier = Purifier()

    db.commit()

    return list(
        db.scalars(
            select(Room)
            .where(func.lower(Room.name).in_(name.lower() for name in DEMO_ROOM_NAMES))
            .options(selectinload(Room.sensor), selectinload(Room.purifier))
            .order_by(Room.name)
        ).all()
    )


def main() -> None:
    with SessionLocal() as db:
        rooms = seed_demo_rooms(db)

    print("Demo rooms are ready:")
    for room in rooms:
        print(f"- {room.name} (sensor {room.sensor.id}, purifier {room.purifier.id})")


if __name__ == "__main__":
    main()
