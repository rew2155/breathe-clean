import logging
from typing import Annotated

from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import get_db
from models import SensorReading
from schemas import SensorReadingCreate, SensorReadingResponse


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
    "/readings",
    response_model=SensorReadingResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database service is unavailable"
        }
    },
)
def create_reading(reading: SensorReadingCreate, db: DbSession):
    db_reading = SensorReading(
        pm25=reading.pm25
    )

    db.add(db_reading)
    db.commit()
    db.refresh(db_reading)

    return db_reading


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
