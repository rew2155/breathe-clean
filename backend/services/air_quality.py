import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum


DEFAULT_TURN_ON_THRESHOLD = 15.0
DEFAULT_TURN_OFF_THRESHOLD = 8.0
DEFAULT_WINDOW = timedelta(minutes=5)
DEFAULT_MINIMUM_READINGS = 3


class EvaluationStatus(StrEnum):
    READY = "ready"
    INSUFFICIENT_DATA = "insufficient_data"
    STALE = "stale"


@dataclass(frozen=True)
class AirQualitySample:
    pm25: float
    recorded_at: datetime


@dataclass(frozen=True)
class AirQualityEvaluation:
    status: EvaluationStatus
    desired_purifier_state: bool
    reading_count: int
    average_pm25: float | None


def decide_purifier_state(
    pm25_average: float,
    purifier_is_on: bool,
    *,
    turn_on_threshold: float = DEFAULT_TURN_ON_THRESHOLD,
    turn_off_threshold: float = DEFAULT_TURN_OFF_THRESHOLD,
) -> bool:
    """Return the desired purifier state for an average PM2.5 reading."""
    values = (pm25_average, turn_on_threshold, turn_off_threshold)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("PM2.5 values and thresholds must be finite")
    if pm25_average < 0:
        raise ValueError("PM2.5 average cannot be negative")
    if turn_off_threshold >= turn_on_threshold:
        raise ValueError(
            "Turn-off threshold must be lower than turn-on threshold"
        )

    if purifier_is_on:
        return pm25_average > turn_off_threshold

    return pm25_average >= turn_on_threshold


def evaluate_air_quality(
    samples: Iterable[AirQualitySample],
    purifier_is_on: bool,
    *,
    now: datetime | None = None,
    window: timedelta = DEFAULT_WINDOW,
    minimum_readings: int = DEFAULT_MINIMUM_READINGS,
) -> AirQualityEvaluation:
    """Evaluate recent samples and return the desired purifier state."""
    evaluation_time = now or datetime.now(timezone.utc)
    if evaluation_time.tzinfo is None:
        raise ValueError("Evaluation time must include a timezone")
    if window <= timedelta(0):
        raise ValueError("Averaging window must be positive")
    if minimum_readings < 1:
        raise ValueError("Minimum readings must be at least one")

    all_samples = list(samples)
    for sample in all_samples:
        if sample.recorded_at.tzinfo is None:
            raise ValueError("Sample timestamps must include a timezone")
        if not math.isfinite(sample.pm25) or sample.pm25 < 0:
            raise ValueError("Sample PM2.5 values must be finite and non-negative")

    window_start = evaluation_time - window
    recent_samples = [
        sample
        for sample in all_samples
        if window_start <= sample.recorded_at <= evaluation_time
    ]

    if not recent_samples:
        status = (
            EvaluationStatus.STALE
            if all_samples
            else EvaluationStatus.INSUFFICIENT_DATA
        )
        return AirQualityEvaluation(
            status=status,
            desired_purifier_state=purifier_is_on,
            reading_count=0,
            average_pm25=None,
        )

    average_pm25 = sum(sample.pm25 for sample in recent_samples) / len(
        recent_samples
    )
    if len(recent_samples) < minimum_readings:
        return AirQualityEvaluation(
            status=EvaluationStatus.INSUFFICIENT_DATA,
            desired_purifier_state=purifier_is_on,
            reading_count=len(recent_samples),
            average_pm25=average_pm25,
        )

    return AirQualityEvaluation(
        status=EvaluationStatus.READY,
        desired_purifier_state=decide_purifier_state(
            average_pm25,
            purifier_is_on,
        ),
        reading_count=len(recent_samples),
        average_pm25=average_pm25,
    )
