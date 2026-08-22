import logging
from collections.abc import Callable
from datetime import datetime, timezone
from enum import StrEnum

from pydantic import ValidationError
from sqlalchemy.orm import Session

from adapters.purifier import PurifierAdapter, PurifierControlError
from messaging.messages import PurifierStateMessage, SensorReadingMessage
from messaging.topics import (
    purifier_id_from_state_topic,
    purifier_state_topic,
    sensor_id_from_readings_topic,
    sensor_readings_topic,
)
from messaging.transport import MessageDisposition, MessageTransport
from models import Purifier
from services.reading_ingestion import (
    DuplicateReadingError,
    PurifierNotConfiguredError,
    SensorNotFoundError,
    ingest_sensor_reading,
)


logger = logging.getLogger(__name__)


class MessageProcessingStatus(StrEnum):
    PROCESSED = "processed"
    IGNORED = "ignored"
    REJECTED = "rejected"
    FAILED = "failed"


class SensorReadingConsumer:
    def __init__(
        self,
        transport: MessageTransport,
        session_factory: Callable[[], Session],
        purifier_adapter: PurifierAdapter,
    ) -> None:
        self.transport = transport
        self.session_factory = session_factory
        self.purifier_adapter = purifier_adapter

    def start(self) -> None:
        self.transport.subscribe(sensor_readings_topic(), self._consume)

    def _consume(self, topic: str, payload: bytes) -> MessageDisposition:
        status = self.handle_message(topic, payload)
        if status is MessageProcessingStatus.FAILED:
            return MessageDisposition.RETRY
        return MessageDisposition.ACKNOWLEDGE

    def handle_message(self, topic: str, payload: bytes) -> MessageProcessingStatus:
        try:
            sensor_id = sensor_id_from_readings_topic(topic)
            message = SensorReadingMessage.model_validate_json(payload)
        except (ValueError, ValidationError):
            logger.warning("Rejected invalid sensor reading message")
            return MessageProcessingStatus.REJECTED

        if message.sensor_id != sensor_id:
            logger.warning("Rejected sensor reading with mismatched topic ID")
            return MessageProcessingStatus.REJECTED

        try:
            with self.session_factory() as db:
                ingest_sensor_reading(
                    db,
                    self.purifier_adapter,
                    sensor_id=message.sensor_id,
                    pm25=message.pm25,
                    recorded_at=message.recorded_at,
                    evaluation_time=datetime.now(timezone.utc),
                    source_message_id=message.message_id,
                )
        except DuplicateReadingError:
            logger.info("Ignored duplicate sensor message %s", message.message_id)
            return MessageProcessingStatus.IGNORED
        except (SensorNotFoundError, PurifierNotConfiguredError):
            logger.warning("Rejected reading for an unconfigured sensor")
            return MessageProcessingStatus.REJECTED
        except PurifierControlError:
            logger.exception("Purifier control failed while processing reading")
            return MessageProcessingStatus.FAILED
        except Exception:
            logger.exception("Unexpected failure processing sensor reading")
            return MessageProcessingStatus.FAILED

        return MessageProcessingStatus.PROCESSED


class PurifierStateConsumer:
    def __init__(
        self,
        transport: MessageTransport,
        session_factory: Callable[[], Session],
    ) -> None:
        self.transport = transport
        self.session_factory = session_factory

    def start(self) -> None:
        self.transport.subscribe(purifier_state_topic(), self._consume)

    def _consume(self, topic: str, payload: bytes) -> MessageDisposition:
        status = self.handle_message(topic, payload)
        if status is MessageProcessingStatus.FAILED:
            return MessageDisposition.RETRY
        return MessageDisposition.ACKNOWLEDGE

    def handle_message(self, topic: str, payload: bytes) -> MessageProcessingStatus:
        try:
            purifier_id = purifier_id_from_state_topic(topic)
            message = PurifierStateMessage.model_validate_json(payload)
        except (ValueError, ValidationError):
            logger.warning("Rejected invalid purifier state message")
            return MessageProcessingStatus.REJECTED

        if message.purifier_id != purifier_id:
            logger.warning("Rejected purifier state with mismatched topic ID")
            return MessageProcessingStatus.REJECTED

        try:
            with self.session_factory() as db:
                purifier = db.get(Purifier, purifier_id)
                if purifier is None:
                    logger.warning(
                        "Ignored state for unknown purifier %s",
                        purifier_id,
                    )
                    return MessageProcessingStatus.IGNORED
                if purifier.pending_command_id != message.command_id:
                    logger.info("Ignored stale state for purifier %s", purifier_id)
                    return MessageProcessingStatus.IGNORED

                purifier.is_on = message.is_on
                purifier.pending_command_id = None
                if purifier.desired_is_on != message.is_on:
                    purifier.desired_is_on = message.is_on
                db.commit()
        except Exception:
            logger.exception("Unexpected failure processing purifier state")
            return MessageProcessingStatus.FAILED

        return MessageProcessingStatus.PROCESSED
