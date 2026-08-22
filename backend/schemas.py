from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from services.air_quality import EvaluationStatus


class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class SensorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int


class PurifierResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    is_on: bool
    desired_is_on: bool
    pending_command_id: UUID | None


class RoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sensor: SensorResponse
    purifier: PurifierResponse


class SensorReadingCreate(BaseModel):
    pm25: float = Field(ge=0)
    sensor_id: int = Field(gt=0)


class SensorReadingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pm25: float
    created_at: datetime
    sensor_id: int
    source_message_id: UUID | None


class AirQualityEvaluationResponse(BaseModel):
    status: EvaluationStatus
    desired_purifier_state: bool
    reading_count: int
    average_pm25: float | None


class ReadingIngestionResponse(BaseModel):
    reading: SensorReadingResponse
    evaluation: AirQualityEvaluationResponse
