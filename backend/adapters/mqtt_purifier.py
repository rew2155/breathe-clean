from collections.abc import Callable
from datetime import datetime, timezone
from uuid import UUID, uuid4

from adapters.purifier import PurifierControlError, PurifierControlResult
from messaging.messages import PurifierCommandMessage
from messaging.topics import purifier_commands_topic
from messaging.transport import MessageTransport, MqttTransportError


class MqttPurifierAdapter:
    def __init__(
        self,
        transport: MessageTransport,
        *,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.transport = transport
        self.id_factory = id_factory
        self.clock = clock

    def set_state(
        self,
        purifier_id: int,
        desired_state: bool,
    ) -> PurifierControlResult:
        command_id = self.id_factory()
        command = PurifierCommandMessage(
            message_id=command_id,
            purifier_id=purifier_id,
            desired_state=desired_state,
            issued_at=self.clock(),
        )

        try:
            self.transport.publish(
                purifier_commands_topic(purifier_id),
                command,
            )
        except MqttTransportError as exc:
            raise PurifierControlError(
                f"Unable to publish command for purifier {purifier_id}"
            ) from exc

        return PurifierControlResult(
            state_confirmed=False,
            command_id=command_id,
        )
