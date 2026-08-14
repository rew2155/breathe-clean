import secrets
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def generate_id() -> int:
    return secrets.randbelow(2**63)


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        default=generate_id
    )

    pm25: Mapped[float] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )