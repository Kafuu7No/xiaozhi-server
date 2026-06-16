import unittest

from app.core.config import get_settings
from app.services.sensor_service import build_alerts


class SensorServiceTests(unittest.TestCase):
    def setUp(self):
        get_settings.cache_clear()

    def tearDown(self):
        get_settings.cache_clear()

    def test_build_alerts_defaults_to_config_thresholds(self):
        # Config sensor_temp_max default is 35.0.
        alerts = build_alerts(36.0, 50.0)
        self.assertTrue(alerts["temp_high"])

    def test_build_alerts_respects_custom_thresholds(self):
        thresholds = {"temp_max": 40.0, "humid_min": 20.0, "humid_max": 90.0}
        self.assertFalse(build_alerts(36.0, 50.0, thresholds)["temp_high"])
        self.assertTrue(build_alerts(42.0, 50.0, thresholds)["temp_high"])
        self.assertTrue(build_alerts(36.0, 15.0, thresholds)["humi_low"])
        self.assertEqual(build_alerts(36.0, 50.0, thresholds)["thresholds"]["temp_max"], 40.0)


if __name__ == "__main__":
    unittest.main()
