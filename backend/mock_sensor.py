import os
import random
import time
from dataclasses import dataclass

import requests


API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
INTERVAL_SECONDS = int(os.getenv("SIMULATION_INTERVAL_SECONDS", "240"))
REQUEST_TIMEOUT_SECONDS = 10

STARTING_PM25 = {
    "Master Bedroom": 8.0,
    "Living Room": 12.0,
    "Kitchen": 19.0,
    "Home Office": 10.0,
}


@dataclass
class SimulatedRoom:
    pm25: float


def next_pm25(current: float, purifier_is_on: bool, rng: random.Random) -> float:
    """Model slow pollution changes and a purifier that removes particulates."""
    purifier_effect = -3.2 if purifier_is_on else 0.35
    household_noise = rng.uniform(-1.0, 1.0)
    pollution_event = rng.uniform(3.0, 8.0) if rng.random() < 0.08 else 0.0
    updated = current + purifier_effect + household_noise + pollution_event
    return round(max(1.0, min(75.0, updated)), 1)


def get_rooms(session: requests.Session) -> list[dict]:
    response = session.get(
        f"{API_BASE_URL}/rooms",
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def publish_cycle(
    session: requests.Session,
    states: dict[int, SimulatedRoom],
    rng: random.Random,
) -> None:
    rooms = get_rooms(session)
    if not rooms:
        raise RuntimeError("No rooms exist. Run `python seed.py` first.")

    for room in rooms:
        sensor_id = room["sensor"]["id"]
        state = states.setdefault(
            sensor_id,
            SimulatedRoom(STARTING_PM25.get(room["name"], 10.0)),
        )
        state.pm25 = next_pm25(
            state.pm25,
            room["purifier"]["is_on"],
            rng,
        )
        response = session.post(
            f"{API_BASE_URL}/readings",
            json={"sensor_id": sensor_id, "pm25": state.pm25},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        evaluation = response.json()["evaluation"]
        purifier_state = (
            "on" if evaluation["desired_purifier_state"] else "off"
        )
        print(
            f'{room["name"]}: {state.pm25:.1f} µg/m³ | '
            f"purifier {purifier_state} | {evaluation['status']}",
            flush=True,
        )


def main() -> None:
    if INTERVAL_SECONDS <= 0:
        raise ValueError("SIMULATION_INTERVAL_SECONDS must be positive")

    states: dict[int, SimulatedRoom] = {}
    rng = random.Random()
    with requests.Session() as session:
        print(
            f"Home simulator started; publishing every {INTERVAL_SECONDS} "
            "seconds. Press Ctrl+C to stop.",
            flush=True,
        )
        try:
            while True:
                try:
                    publish_cycle(session, states, rng)
                except (requests.RequestException, RuntimeError) as exc:
                    print(f"Simulation cycle failed: {exc}", flush=True)
                time.sleep(INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\nHome simulator stopped.")


if __name__ == "__main__":
    main()
