import unittest

from app.core.config import get_settings
from app.services.sensor_pipeline import (
    build_sensor_alerts,
    parse_sensor_payload,
    parse_sensor_recorded_at,
)


class SensorPipelineTests(unittest.TestCase):
    def setUp(self):
        get_settings.cache_clear()

    def tearDown(self):
        get_settings.cache_clear()

    def test_parse_direct_sensor_message(self):
        parsed = parse_sensor_payload({"temperature": 25.6, "humidity": 61.2})
        self.assertEqual(parsed, {"temperature": 25.6, "humidity": 61.2})

    def test_parse_device_env_message(self):
        parsed = parse_sensor_payload({"temp_c": 25.6, "humi_rh": 61.2})
        self.assertEqual(parsed, {"temperature": 25.6, "humidity": 61.2})

    def test_parse_iot_sensor_state(self):
        parsed = parse_sensor_payload(
            {
                "type": "iot",
                "states": [
                    {"name": "Speaker", "state": {"volume": 70}},
                    {"name": "AHT20", "state": {"temperature": 26.4, "humidity": 58.0}},
                ],
            }
        )
        self.assertEqual(parsed, {"temperature": 26.4, "humidity": 58.0})

    def test_parse_nested_payload(self):
        parsed = parse_sensor_payload(
            {"payload": {"result": {"temperature": "27.1", "humidity": "42.5"}}}
        )
        self.assertEqual(parsed, {"temperature": 27.1, "humidity": 42.5})

    def test_parse_nested_timestamp(self):
        recorded_at = parse_sensor_recorded_at(
            {"data": {"temperature": 27.1, "humidity": 42.5, "timestamp": 1714200000}}
        )
        self.assertEqual(recorded_at.isoformat(), "2024-04-27T06:40:00")

    def test_build_sensor_alerts(self):
        alerts = build_sensor_alerts(temperature=36.0, humidity=20.0)
        self.assertTrue(alerts["temperature_high"])
        self.assertTrue(alerts["humidity_low"])
        self.assertFalse(alerts["humidity_high"])
        self.assertEqual(alerts["thresholds"]["temp_max"], 35.0)


if __name__ == "__main__":
    unittest.main()
