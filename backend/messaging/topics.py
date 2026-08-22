TOPIC_PREFIX = "breathe-clean/v1"


def sensor_readings_topic(sensor_id: int | str = "+") -> str:
    return f"{TOPIC_PREFIX}/sensors/{_device_segment(sensor_id)}/readings"


def sensor_id_from_readings_topic(topic: str) -> int:
    return _device_id_from_topic(topic, device_type="sensors", suffix="readings")


def purifier_commands_topic(purifier_id: int | str = "+") -> str:
    return f"{TOPIC_PREFIX}/purifiers/{_device_segment(purifier_id)}/commands"


def purifier_state_topic(purifier_id: int | str = "+") -> str:
    return f"{TOPIC_PREFIX}/purifiers/{_device_segment(purifier_id)}/state"


def purifier_id_from_state_topic(topic: str) -> int:
    return _device_id_from_topic(topic, device_type="purifiers", suffix="state")


def _device_id_from_topic(
    topic: str,
    *,
    device_type: str,
    suffix: str,
) -> int:
    parts = topic.split("/")
    if (
        len(parts) != 5
        or parts[:3] != ["breathe-clean", "v1", device_type]
        or parts[4] != suffix
    ):
        raise ValueError("Invalid device topic")
    try:
        device_id = int(parts[3])
    except ValueError as exc:
        raise ValueError("Invalid device ID in topic") from exc
    if device_id <= 0:
        raise ValueError("Device ID in topic must be positive")
    return device_id


def _device_segment(device_id: int | str) -> str:
    if device_id == "+":
        return device_id
    if not isinstance(device_id, int) or isinstance(device_id, bool):
        raise TypeError("Device ID must be a positive integer or '+'")
    if device_id <= 0:
        raise ValueError("Device ID must be positive")
    return str(device_id)
