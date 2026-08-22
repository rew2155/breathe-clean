import random
import unittest

from mock_sensor import next_pm25


class MockSensorTests(unittest.TestCase):
    def test_purifier_reduces_pm25(self):
        result = next_pm25(20, purifier_is_on=True, rng=random.Random(1))
        self.assertLess(result, 20)

    def test_reading_stays_in_sensor_range(self):
        self.assertGreaterEqual(
            next_pm25(0, purifier_is_on=True, rng=random.Random(1)),
            1,
        )
        self.assertLessEqual(
            next_pm25(100, purifier_is_on=False, rng=random.Random(1)),
            75,
        )


if __name__ == "__main__":
    unittest.main()
