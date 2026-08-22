import unittest
from datetime import datetime, timedelta, timezone

from services.air_quality import (
    AirQualitySample,
    EvaluationStatus,
    decide_purifier_state,
    evaluate_air_quality,
)


class DecidePurifierStateTests(unittest.TestCase):
    def test_turns_off_purifier_on_at_high_pm25(self):
        self.assertTrue(decide_purifier_state(20, purifier_is_on=False))
        self.assertTrue(decide_purifier_state(15, purifier_is_on=False))

    def test_keeps_off_purifier_off_inside_hysteresis_band(self):
        self.assertFalse(decide_purifier_state(12, purifier_is_on=False))

    def test_keeps_on_purifier_on_inside_hysteresis_band(self):
        self.assertTrue(decide_purifier_state(12, purifier_is_on=True))

    def test_turns_on_purifier_off_at_low_pm25(self):
        self.assertFalse(decide_purifier_state(8, purifier_is_on=True))
        self.assertFalse(decide_purifier_state(5, purifier_is_on=True))

    def test_rejects_negative_average(self):
        with self.assertRaises(ValueError):
            decide_purifier_state(-1, purifier_is_on=False)

    def test_rejects_non_finite_values(self):
        for value in (float("inf"), float("-inf"), float("nan")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    decide_purifier_state(value, purifier_is_on=False)

    def test_rejects_invalid_threshold_order(self):
        with self.assertRaises(ValueError):
            decide_purifier_state(
                10,
                purifier_is_on=False,
                turn_on_threshold=8,
                turn_off_threshold=15,
            )

    def test_supports_custom_thresholds(self):
        self.assertTrue(
            decide_purifier_state(
                20,
                purifier_is_on=False,
                turn_on_threshold=20,
                turn_off_threshold=10,
            )
        )


class EvaluateAirQualityTests(unittest.TestCase):
    now = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)

    def sample(self, pm25: float, minutes_ago: float) -> AirQualitySample:
        return AirQualitySample(
            pm25=pm25,
            recorded_at=self.now - timedelta(minutes=minutes_ago),
        )

    def test_uses_only_readings_inside_five_minute_window(self):
        evaluation = evaluate_air_quality(
            [
                self.sample(20, 1),
                self.sample(16, 2),
                self.sample(12, 3),
                self.sample(100, 6),
            ],
            purifier_is_on=False,
            now=self.now,
        )

        self.assertEqual(evaluation.status, EvaluationStatus.READY)
        self.assertEqual(evaluation.reading_count, 3)
        self.assertEqual(evaluation.average_pm25, 16)
        self.assertTrue(evaluation.desired_purifier_state)

    def test_supports_available_readings_at_four_minute_intervals(self):
        evaluation = evaluate_air_quality(
            [
                self.sample(20, 0),
                self.sample(18, 4),
                self.sample(16, 8),
            ],
            purifier_is_on=False,
            now=self.now,
        )

        self.assertEqual(evaluation.status, EvaluationStatus.READY)
        self.assertEqual(evaluation.reading_count, 2)
        self.assertEqual(evaluation.average_pm25, 19)
        self.assertTrue(evaluation.desired_purifier_state)

    def test_acts_on_two_recent_readings(self):
        evaluation = evaluate_air_quality(
            [self.sample(20, 1), self.sample(20, 2)],
            purifier_is_on=False,
            now=self.now,
        )

        self.assertEqual(evaluation.status, EvaluationStatus.READY)
        self.assertTrue(evaluation.desired_purifier_state)

    def test_acts_on_one_recent_reading(self):
        evaluation = evaluate_air_quality(
            [self.sample(20, 1)],
            purifier_is_on=False,
            now=self.now,
        )

        self.assertEqual(evaluation.status, EvaluationStatus.READY)
        self.assertEqual(evaluation.reading_count, 1)
        self.assertTrue(evaluation.desired_purifier_state)

    def test_reports_stale_when_only_old_readings_exist(self):
        evaluation = evaluate_air_quality(
            [self.sample(20, 6)],
            purifier_is_on=True,
            now=self.now,
        )

        self.assertEqual(evaluation.status, EvaluationStatus.STALE)
        self.assertTrue(evaluation.desired_purifier_state)
        self.assertIsNone(evaluation.average_pm25)

    def test_reports_insufficient_data_when_sensor_has_no_readings(self):
        evaluation = evaluate_air_quality(
            [],
            purifier_is_on=False,
            now=self.now,
        )

        self.assertEqual(
            evaluation.status,
            EvaluationStatus.INSUFFICIENT_DATA,
        )
        self.assertFalse(evaluation.desired_purifier_state)

    def test_rejects_naive_timestamps(self):
        with self.assertRaises(ValueError):
            evaluate_air_quality(
                [AirQualitySample(pm25=10, recorded_at=datetime(2026, 8, 21))],
                purifier_is_on=False,
                now=self.now,
            )


if __name__ == "__main__":
    unittest.main()
