from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: UUID


class SensorReadingMessage(Message):
    sensor_id: int = Field(gt=0)
    pm25: float = Field(ge=0, allow_inf_nan=False)
    recorded_at: AwareDatetime


class PurifierCommandMessage(Message):
    purifier_id: int = Field(gt=0)
    desired_state: bool
    issued_at: AwareDatetime


class PurifierStateMessage(Message):
    command_id: UUID
    purifier_id: int = Field(gt=0)
    is_on: bool
    observed_at: AwareDatetime
