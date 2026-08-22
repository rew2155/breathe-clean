import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from database import get_db
from models import Purifier, Room, Sensor, SensorReading
from schemas import (
    AirQualityEvaluationResponse,
    ReadingIngestionResponse,
    RoomCreate,
    RoomResponse,
    SensorReadingCreate,
    SensorReadingResponse,
)
from services.air_quality import (
    DEFAULT_WINDOW,
    AirQualitySample,
    evaluate_air_quality,
)


logger = logging.getLogger(__name__)
app = FastAPI()
DbSession = Annotated[Session, Depends(get_db)]


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(
    request: Request,
    exc: SQLAlchemyError,
) -> JSONResponse:
    logger.error(
        "Database operation failed for %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Database service is unavailable"},
    )


@app.post(
    "/rooms",
    response_model=RoomResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "A room with this name already exists"
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database service is unavailable"
        },
    },
)
def create_room(room: RoomCreate, db: DbSession):
    db_room = Room(
        name=room.name,
        sensor=Sensor(),
        purifier=Purifier(),
    )

    db.add(db_room)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A room with this name already exists",
        ) from exc

    db.refresh(db_room)
    return db_room


@app.get(
    "/rooms",
    response_model=list[RoomResponse],
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database service is unavailable"
        }
    },
)
def get_rooms(db: DbSession):
    return db.scalars(
        select(Room)
        .options(
            selectinload(Room.sensor),
            selectinload(Room.purifier),
        )
        .order_by(Room.name)
    ).all()


@app.post(
    "/readings",
    response_model=ReadingIngestionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Sensor does not exist"
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database service is unavailable"
        }
    },
)
def create_reading(reading: SensorReadingCreate, db: DbSession):
    sensor = db.get(Sensor, reading.sensor_id)
    if sensor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sensor not found",
        )

    purifier = db.scalar(
        select(Purifier).where(Purifier.room_id == sensor.room_id)
    )
    if purifier is None:
        raise SQLAlchemyError("Sensor room does not have a purifier")

    db_reading = SensorReading(
        pm25=reading.pm25,
        sensor_id=reading.sensor_id,
    )

    db.add(db_reading)
    db.flush()

    evaluation_time = datetime.now(timezone.utc)
    recent_readings = db.scalars(
        select(SensorReading).where(
            SensorReading.sensor_id == sensor.id,
            SensorReading.created_at >= evaluation_time - DEFAULT_WINDOW,
            SensorReading.created_at <= evaluation_time,
        )
    ).all()
    samples = [
        AirQualitySample(
            pm25=recent_reading.pm25,
            recorded_at=(
                recent_reading.created_at
                if recent_reading.created_at.tzinfo is not None
                else recent_reading.created_at.replace(tzinfo=timezone.utc)
            ),
        )
        for recent_reading in recent_readings
    ]
    evaluation = evaluate_air_quality(
        samples,
        purifier_is_on=purifier.is_on,
        now=evaluation_time,
    )

    db.commit()
    db.refresh(db_reading)

    return ReadingIngestionResponse(
        reading=SensorReadingResponse.model_validate(db_reading),
        evaluation=AirQualityEvaluationResponse(
            status=evaluation.status,
            desired_purifier_state=evaluation.desired_purifier_state,
            reading_count=evaluation.reading_count,
            average_pm25=evaluation.average_pm25,
        ),
    )


@app.get(
    "/readings",
    response_model=list[SensorReadingResponse],
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database service is unavailable"
        }
    },
)
def get_readings(db: DbSession):
    readings = db.scalars(
        select(SensorReading)
    ).all()

    return readings
