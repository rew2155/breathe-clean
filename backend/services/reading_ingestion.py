from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from adapters.purifier import PurifierAdapter
from models import Purifier, Sensor, SensorReading
from services.air_quality import (
    DEFAULT_WINDOW,
    AirQualityEvaluation,
    AirQualitySample,
    EvaluationStatus,
    evaluate_air_quality,
)


class SensorNotFoundError(Exception):
    """Raised when a reading references an unknown sensor."""


class PurifierNotConfiguredError(Exception):
    """Raised when a sensor's room does not have a purifier."""


class DuplicateReadingError(Exception):
    """Raised when an MQTT message has already been ingested."""


@dataclass(frozen=True)
class ReadingIngestionResult:
    reading: SensorReading
    evaluation: AirQualityEvaluation


def ingest_sensor_reading(
    db: Session,
    purifier_adapter: PurifierAdapter,
    *,
    sensor_id: int,
    pm25: float,
    recorded_at: datetime | None = None,
    evaluation_time: datetime | None = None,
    source_message_id: UUID | None = None,
) -> ReadingIngestionResult:
    now = evaluation_time or datetime.now(timezone.utc)
    reading_time = recorded_at or now

    if source_message_id is not None:
        existing_reading = db.scalar(
            select(SensorReading).where(
                SensorReading.source_message_id == source_message_id
            )
        )
        if existing_reading is not None:
            raise DuplicateReadingError(
                f"Message {source_message_id} was already ingested"
            )

    sensor = db.get(Sensor, sensor_id)
    if sensor is None:
        raise SensorNotFoundError(f"Sensor {sensor_id} does not exist")

    purifier = db.scalar(
        select(Purifier).where(Purifier.room_id == sensor.room_id)
    )
    if purifier is None:
        raise PurifierNotConfiguredError(
            f"Room {sensor.room_id} does not have a purifier"
        )

    db_reading = SensorReading(
        pm25=pm25,
        sensor_id=sensor.id,
        created_at=reading_time,
        source_message_id=source_message_id,
    )
    db.add(db_reading)
    db.flush()

    recent_readings = db.scalars(
        select(SensorReading).where(
            SensorReading.sensor_id == sensor.id,
            SensorReading.created_at >= now - DEFAULT_WINDOW,
            SensorReading.created_at <= now,
        )
    ).all()
    samples = [
        AirQualitySample(
            pm25=recent_reading.pm25,
            recorded_at=_as_utc(recent_reading.created_at),
        )
        for recent_reading in recent_readings
    ]
    evaluation = evaluate_air_quality(
        samples,
        purifier_is_on=purifier.desired_is_on,
        now=now,
    )

    if (
        evaluation.status is EvaluationStatus.READY
        and evaluation.desired_purifier_state != purifier.desired_is_on
    ):
        control_result = purifier_adapter.set_state(
            purifier_id=purifier.id,
            desired_state=evaluation.desired_purifier_state,
        )
        purifier.desired_is_on = evaluation.desired_purifier_state
        purifier.pending_command_id = control_result.command_id
        if control_result.state_confirmed:
            purifier.is_on = evaluation.desired_purifier_state
            purifier.pending_command_id = None

    db.commit()
    db.refresh(db_reading)
    return ReadingIngestionResult(
        reading=db_reading,
        evaluation=evaluation,
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
