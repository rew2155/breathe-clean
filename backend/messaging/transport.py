import os
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from threading import Event
from typing import Protocol

import paho.mqtt.client as mqtt

from messaging.messages import Message


class MessageDisposition(StrEnum):
    ACKNOWLEDGE = "acknowledge"
    RETRY = "retry"


MessageHandler = Callable[[str, bytes], MessageDisposition]


class MqttTransportError(Exception):
    """Raised when the MQTT transport cannot complete an operation."""


class MessageTransport(Protocol):
    def publish(self, topic: str, message: Message) -> None:
        """Publish a validated message."""
        ...

    def subscribe(self, topic: str, handler: MessageHandler) -> None:
        """Register a handler for a subscription topic."""
        ...


@dataclass(frozen=True)
class MqttSettings:
    host: str = "localhost"
    port: int = 1883
    client_id: str = "breathe-clean-backend"
    keepalive: int = 60

    @classmethod
    def from_environment(cls) -> "MqttSettings":
        return cls(
            host=os.getenv("MQTT_HOST", cls.host),
            port=int(os.getenv("MQTT_PORT", cls.port)),
            client_id=os.getenv("MQTT_CLIENT_ID", cls.client_id),
        )


class PahoMqttTransport:
    def __init__(
        self,
        settings: MqttSettings,
        *,
        client: mqtt.Client | None = None,
        operation_timeout: float = 5.0,
    ) -> None:
        self.settings = settings
        self.operation_timeout = operation_timeout
        self._connected = Event()
        self._connection_error: str | None = None
        self._subscriptions: dict[str, MessageHandler] = {}
        self._client = client or mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=settings.client_id,
            manual_ack=True,
        )
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

    def connect(self) -> None:
        self._connection_error = None
        self._connected.clear()
        try:
            self._client.connect(
                self.settings.host,
                self.settings.port,
                self.settings.keepalive,
            )
            self._client.loop_start()
        except (OSError, ValueError) as exc:
            raise MqttTransportError("Unable to connect to MQTT broker") from exc

        if not self._connected.wait(self.operation_timeout):
            self._client.loop_stop()
            raise MqttTransportError(
                self._connection_error or "MQTT broker connection timed out"
            )
        if self._connection_error is not None:
            self._client.loop_stop()
            raise MqttTransportError(self._connection_error)

    def disconnect(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()
        self._connected.clear()

    def publish(self, topic: str, message: Message) -> None:
        if not self._connected.is_set():
            raise MqttTransportError("MQTT transport is not connected")

        result = self._client.publish(
            topic,
            payload=message.model_dump_json(),
            qos=1,
            retain=False,
        )
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise MqttTransportError(
                f"MQTT publish failed with result code {result.rc}"
            )

        try:
            result.wait_for_publish(timeout=self.operation_timeout)
        except RuntimeError as exc:
            raise MqttTransportError("MQTT publish was not acknowledged") from exc
        if not result.is_published():
            raise MqttTransportError("MQTT publish timed out")

    def subscribe(self, topic: str, handler: MessageHandler) -> None:
        self._subscriptions[topic] = handler
        self._client.message_callback_add(topic, self._dispatch_message)
        if self._connected.is_set():
            self._subscribe(topic)

    def _subscribe(self, topic: str) -> None:
        result_code, _ = self._client.subscribe(topic, qos=1)
        if result_code != mqtt.MQTT_ERR_SUCCESS:
            raise MqttTransportError(
                f"MQTT subscribe failed with result code {result_code}"
            )

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code.is_failure:
            self._connection_error = f"MQTT broker rejected connection: {reason_code}"
            self._connected.set()
            return

        try:
            for topic in self._subscriptions:
                self._subscribe(topic)
        except MqttTransportError as exc:
            self._connection_error = str(exc)
        self._connected.set()

    def _on_disconnect(
        self,
        client,
        userdata,
        disconnect_flags,
        reason_code,
        properties,
    ) -> None:
        self._connected.clear()

    def _dispatch_message(self, client, userdata, mqtt_message) -> None:
        dispositions = []
        for topic_filter, handler in self._subscriptions.items():
            if mqtt.topic_matches_sub(topic_filter, mqtt_message.topic):
                dispositions.append(
                    handler(mqtt_message.topic, mqtt_message.payload)
                )

        if dispositions and MessageDisposition.RETRY not in dispositions:
            result_code = self._client.ack(mqtt_message.mid, mqtt_message.qos)
            if result_code != mqtt.MQTT_ERR_SUCCESS:
                raise MqttTransportError(
                    f"MQTT acknowledgment failed with result code {result_code}"
                )
