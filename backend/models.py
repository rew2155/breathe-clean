import secrets
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def generate_id() -> int:
    return secrets.randbelow(2**63 - 1) + 1


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        default=generate_id,
    )
    name: Mapped[str] = mapped_column(String(100))
    __table_args__ = (
        Index("uq_rooms_name_lower", func.lower(name), unique=True),
    )

    sensor: Mapped["Sensor | None"] = relationship(back_populates="room")
    purifier: Mapped["Purifier | None"] = relationship(back_populates="room")


class Sensor(Base):
    __tablename__ = "sensors"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        default=generate_id,
    )
    room_id: Mapped[int] = mapped_column(
        ForeignKey("rooms.id"),
        unique=True,
    )

    room: Mapped[Room] = relationship(back_populates="sensor")
    readings: Mapped[list["SensorReading"]] = relationship(
        back_populates="sensor"
    )


class Purifier(Base):
    __tablename__ = "purifiers"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        default=generate_id,
    )
    room_id: Mapped[int] = mapped_column(
        ForeignKey("rooms.id"),
        unique=True,
    )
    is_on: Mapped[bool] = mapped_column(Boolean, default=False)

    room: Mapped[Room] = relationship(back_populates="purifier")


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        default=generate_id,
    )
    pm25: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    sensor_id: Mapped[int] = mapped_column(
        ForeignKey("sensors.id"),
        index=True,
    )

    sensor: Mapped[Sensor] = relationship(back_populates="readings")
