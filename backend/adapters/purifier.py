from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID


class PurifierControlError(Exception):
    """Raised when a purifier cannot apply a requested state."""


class PurifierAdapter(Protocol):
    def set_state(
        self,
        purifier_id: int,
        desired_state: bool,
    ) -> "PurifierControlResult":
        """Apply the desired state to a purifier or raise an error."""
        ...


@dataclass(frozen=True)
class PurifierCommand:
    purifier_id: int
    desired_state: bool


@dataclass(frozen=True)
class PurifierControlResult:
    state_confirmed: bool
    command_id: UUID | None = None


@dataclass
class SimulatedPurifierAdapter:
    should_fail: bool = False
    commands: list[PurifierCommand] = field(default_factory=list, init=False)

    def set_state(
        self,
        purifier_id: int,
        desired_state: bool,
    ) -> PurifierControlResult:
        if purifier_id <= 0:
            raise ValueError("Purifier ID must be positive")
        if not isinstance(desired_state, bool):
            raise TypeError("Desired purifier state must be a Boolean")

        command = PurifierCommand(
            purifier_id=purifier_id,
            desired_state=desired_state,
        )
        self.commands.append(command)

        if self.should_fail:
            raise PurifierControlError(
                f"Simulated failure controlling purifier {purifier_id}"
            )

        return PurifierControlResult(state_confirmed=True)


simulated_purifier_adapter = SimulatedPurifierAdapter()


def get_purifier_adapter() -> PurifierAdapter:
    return simulated_purifier_adapter
