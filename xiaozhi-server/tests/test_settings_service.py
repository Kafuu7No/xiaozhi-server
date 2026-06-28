import unittest
from math import nan
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.routers.api import AppSettingsRequest
from app.models.database import AppSetting
from app.services.settings_service import (
    MIN_CONFIDENCE,
    SettingsValidationError,
    get_or_create,
    serialize_settings,
    to_db_fields,
    validate_settings_payload,
)


class SettingsServiceTests(unittest.TestCase):
    def test_serialize_settings_uses_camel_case(self):
        setting = AppSetting(
            id=1,
            meow_threshold=0.75,
            meow_min_confidence=MIN_CONFIDENCE,
            temp_max=33.0,
            humid_min=25.0,
            humid_max=85.0,
            auto_on_meow=True,
            delay_seconds=20,
        )
        data = serialize_settings(setting)
        self.assertEqual(data["meowThreshold"], 0.75)
        self.assertEqual(data["meowMinConfidence"], MIN_CONFIDENCE)
        self.assertEqual(data["tempMax"], 33.0)
        self.assertEqual(data["humidMin"], 25.0)
        self.assertEqual(data["humidMax"], 85.0)
        self.assertEqual(data["autoOnMeow"], True)
        self.assertEqual(data["delaySeconds"], 20)

    def test_to_db_fields_maps_camel_to_snake(self):
        result = to_db_fields(
            {
                "meowThreshold": 0.7,
                "meowMinConfidence": 0.45,
                "tempMax": 30.0,
                "autoOnMeow": False,
                "delaySeconds": 5,
            }
        )
        self.assertEqual(
            result,
            {
                "meow_threshold": 0.7,
                "meow_min_confidence": 0.45,
                "temp_max": 30.0,
                "auto_on_meow": False,
                "delay_seconds": 5,
            },
        )

    def test_to_db_fields_drops_none_and_unknown_keys(self):
        result = to_db_fields({"tempMax": None, "humidMax": 90.0, "bogus": 123})
        self.assertEqual(result, {"humid_max": 90.0})

    def test_validate_settings_payload_rejects_invalid_meow_min_confidence(self):
        with self.assertRaises(SettingsValidationError):
            validate_settings_payload({"meowMinConfidence": 0.05})
        with self.assertRaises(SettingsValidationError):
            validate_settings_payload({"meowMinConfidence": 1.0})
        with self.assertRaises(SettingsValidationError):
            validate_settings_payload({"meowMinConfidence": "bad"})
        with self.assertRaises(SettingsValidationError):
            validate_settings_payload({"meowMinConfidence": nan})

    def test_validate_settings_payload_accepts_frontend_meow_min_confidence_range(self):
        validate_settings_payload({"meowMinConfidence": 0.1})
        validate_settings_payload({"meowMinConfidence": 0.95})

    def test_app_settings_request_rejects_invalid_meow_min_confidence(self):
        with self.assertRaises(ValidationError):
            AppSettingsRequest(meowMinConfidence=0.05)
        with self.assertRaises(ValidationError):
            AppSettingsRequest(meowMinConfidence=1.0)


if __name__ == "__main__":
    unittest.main()


@pytest.mark.asyncio
async def test_get_or_create_recovers_when_default_row_is_created_concurrently():
    existing = AppSetting(id=1, meow_min_confidence=MIN_CONFIDENCE)

    class FakeDb:
        def __init__(self):
            self.get = AsyncMock(side_effect=[None, existing])
            self.add = Mock()
            self.commit = AsyncMock(
                side_effect=IntegrityError("insert app_settings", {}, Exception("duplicate"))
            )
            self.rollback = AsyncMock()
            self.refresh = AsyncMock()

    db = FakeDb()

    setting = await get_or_create(db)

    assert setting is existing
    db.add.assert_called_once()
    db.rollback.assert_awaited_once()
    db.refresh.assert_not_awaited()
