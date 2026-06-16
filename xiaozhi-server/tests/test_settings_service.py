import unittest

from app.models.database import AppSetting
from app.services.settings_service import serialize_settings, to_db_fields


class SettingsServiceTests(unittest.TestCase):
    def test_serialize_settings_uses_camel_case(self):
        setting = AppSetting(
            id=1,
            meow_threshold=0.75,
            temp_max=33.0,
            humid_min=25.0,
            humid_max=85.0,
            auto_on_meow=True,
            delay_seconds=20,
        )
        data = serialize_settings(setting)
        self.assertEqual(data["meowThreshold"], 0.75)
        self.assertEqual(data["meowMinConfidence"], 0.5)
        self.assertEqual(data["tempMax"], 33.0)
        self.assertEqual(data["humidMin"], 25.0)
        self.assertEqual(data["humidMax"], 85.0)
        self.assertEqual(data["autoOnMeow"], True)
        self.assertEqual(data["delaySeconds"], 20)

    def test_to_db_fields_maps_camel_to_snake(self):
        result = to_db_fields(
            {"meowThreshold": 0.7, "tempMax": 30.0, "autoOnMeow": False, "delaySeconds": 5}
        )
        self.assertEqual(
            result,
            {
                "meow_threshold": 0.7,
                "temp_max": 30.0,
                "auto_on_meow": False,
                "delay_seconds": 5,
            },
        )

    def test_to_db_fields_drops_none_and_unknown_keys(self):
        result = to_db_fields({"tempMax": None, "humidMax": 90.0, "bogus": 123})
        self.assertEqual(result, {"humid_max": 90.0})


if __name__ == "__main__":
    unittest.main()
