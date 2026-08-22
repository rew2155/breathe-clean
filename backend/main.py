import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from adapters.purifier import (
    PurifierAdapter,
    PurifierControlError,
    SimulatedPurifierAdapter,
)
from adapters.mqtt_purifier import MqttPurifierAdapter
from database import get_db
from database import SessionLocal
from messaging.consumers import PurifierStateConsumer, SensorReadingConsumer
from messaging.transport import MqttSettings, PahoMqttTransport
from models import Purifier, Room, Sensor, SensorReading
from schemas import (
    AirQualityEvaluationResponse,
    ReadingIngestionResponse,
    RoomCreate,
    RoomResponse,
    SensorReadingCreate,
    SensorReadingResponse,
)
from services.reading_ingestion import (
    PurifierNotConfiguredError,
    SensorNotFoundError,
    ingest_sensor_reading,
)


logger = logging.getLogger(__name__)


def mqtt_is_enabled() -> bool:
    value = os.getenv("MQTT_ENABLED", "false").lower()
    if value not in {"true", "false"}:
        raise ValueError("MQTT_ENABLED must be 'true' or 'false'")
    return value == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    transport = None
    if mqtt_is_enabled():
        transport = PahoMqttTransport(MqttSettings.from_environment())
        purifier_adapter: PurifierAdapter = MqttPurifierAdapter(transport)
        SensorReadingConsumer(
            transport,
            SessionLocal,
            purifier_adapter,
        ).start()
        PurifierStateConsumer(transport, SessionLocal).start()
        await asyncio.to_thread(transport.connect)
    else:
        purifier_adapter = SimulatedPurifierAdapter()

    app.state.purifier_adapter = purifier_adapter
    app.state.mqtt_transport = transport
    try:
        yield
    finally:
        if transport is not None:
            await asyncio.to_thread(transport.disconnect)


def get_purifier_controller(request: Request) -> PurifierAdapter:
    return request.app.state.purifier_adapter


app = FastAPI(lifespan=lifespan)
DbSession = Annotated[Session, Depends(get_db)]
PurifierController = Annotated[
    PurifierAdapter,
    Depends(get_purifier_controller),
]


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


@app.exception_handler(PurifierControlError)
async def purifier_control_error_handler(
    request: Request,
    exc: PurifierControlError,
) -> JSONResponse:
    logger.error(
        "Purifier control failed for %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Purifier control service is unavailable"},
    )


@app.exception_handler(PurifierNotConfiguredError)
async def purifier_configuration_error_handler(
    request: Request,
    exc: PurifierNotConfiguredError,
) -> JSONResponse:
    logger.error(
        "Purifier configuration error for %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Purifier is not configured for this sensor"},
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
            "description": "Database or purifier control is unavailable"
        }
    },
)
def create_reading(
    reading: SensorReadingCreate,
    db: DbSession,
    purifier_adapter: PurifierController,
):
    try:
        result = ingest_sensor_reading(
            db,
            purifier_adapter,
            sensor_id=reading.sensor_id,
            pm25=reading.pm25,
        )
    except SensorNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sensor not found",
        ) from exc

    return ReadingIngestionResponse(
        reading=SensorReadingResponse.model_validate(result.reading),
        evaluation=AirQualityEvaluationResponse(
            status=result.evaluation.status,
            desired_purifier_state=(
                result.evaluation.desired_purifier_state
            ),
            reading_count=result.evaluation.reading_count,
            average_pm25=result.evaluation.average_pm25,
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
