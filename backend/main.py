from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import select

from database import SessionLocal
from models import SensorReading


app = FastAPI()


class SensorReadingCreate(BaseModel):
    pm25: float


@app.post("/readings")
async def create_reading(reading: SensorReadingCreate):
    with SessionLocal() as db:
        db_reading = SensorReading(
            pm25=reading.pm25
        )

        db.add(db_reading)
        db.commit()
        db.refresh(db_reading)

        return db_reading


@app.get("/readings")
async def get_readings():
    with SessionLocal() as db:
        readings = db.scalars(
            select(SensorReading)
        ).all()

        return readings