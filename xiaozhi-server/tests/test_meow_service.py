import unittest
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from app.services.meow_service import get_events, get_stats, parse_meow_payload, save_event


class MeowServiceTests(unittest.TestCase):
    def test_parse_direct_meow_message(self):
        parsed = parse_meow_payload({"score": 0.87, "is_cat": True, "ts": 1714200000})
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["score"], 0.87)
        self.assertTrue(parsed["is_cat"])
        self.assertTrue(parsed["device_is_cat"])
        self.assertEqual(parsed["ts"], 1714200000)

    def test_parse_nested_meow_message(self):
        parsed = parse_meow_payload({"data": {"score": "0.73", "is_cat": "false"}})
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["score"], 0.73)
        self.assertFalse(parsed["device_is_cat"])
        self.assertTrue(parsed["is_cat"])

    def test_infer_is_cat_from_score(self):
        parsed = parse_meow_payload({"data": {"score": 0.92}})
        self.assertIsNotNone(parsed)
        self.assertTrue(parsed["is_cat"])

    def test_keep_confidence_compatibility(self):
        parsed = parse_meow_payload({"confidence": 0.66, "confirmed_detected": 0})
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["score"], 0.66)
        self.assertFalse(parsed["device_is_cat"])
        self.assertTrue(parsed["is_cat"])

    def test_infer_is_cat_uses_custom_threshold(self):
        self.assertTrue(parse_meow_payload({"score": 0.7}, threshold=0.6)["is_cat"])
        self.assertFalse(parse_meow_payload({"score": 0.7}, threshold=0.9)["is_cat"])

    def test_custom_threshold_applies_to_nested_payload(self):
        parsed = parse_meow_payload({"data": {"score": 0.65}}, threshold=0.6)
        self.assertTrue(parsed["is_cat"])

    def test_cloud_threshold_overrides_device_label(self):
        parsed = parse_meow_payload({"score": 0.7, "is_cat": True}, threshold=0.8)
        self.assertTrue(parsed["device_is_cat"])
        self.assertFalse(parsed["is_cat"])


if __name__ == "__main__":
    unittest.main()


@pytest.mark.asyncio
async def test_custom_min_confidence_controls_save_list_and_stats():
    high_event = Mock(confidence=0.85, is_cat=True, recorded_at=datetime.now())

    class FakeScalarResult:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    class FakeResult:
        def __init__(self, rows=None, scalar_values=None):
            self._rows = rows or []
            self._scalar_values = list(scalar_values or [])

        def scalars(self):
            return FakeScalarResult(self._rows)

        def scalar_one(self):
            return self._scalar_values.pop(0)

    class FakeDb:
        def __init__(self):
            self.add = Mock()
            self.commit = AsyncMock()
            self.refresh = AsyncMock()
            self.statements = []
            self.statement_params = []
            self._results = [
                FakeResult(rows=[high_event]),
                FakeResult(scalar_values=[1]),
                FakeResult(scalar_values=[1]),
                FakeResult(scalar_values=[0]),
            ]

        async def execute(self, statement):
            self.statements.append(str(statement))
            self.statement_params.append(statement.compile().params)
            return self._results.pop(0)

    db = FakeDb()

    dropped = await save_event(
        db,
        device_id="test-device",
        score=0.45,
        is_cat=True,
        min_confidence=0.5,
    )
    assert dropped["status"] == "dropped"
    assert dropped["min_confidence"] == 0.5
    db.add.assert_not_called()

    stored = await save_event(
        db,
        device_id="test-device",
        score=0.85,
        is_cat=True,
        recorded_at=high_event.recorded_at,
        min_confidence=0.5,
    )
    assert stored["min_confidence"] == 0.5
    db.add.assert_called_once()

    await get_events(db, hours=24, min_confidence=0.5)
    stats = await get_stats(db, min_confidence=0.5)

    assert stats["min_confidence"] == 0.5
    executed_sql = "\n".join(db.statements)
    assert "meow_events.confidence >= :confidence_1" in executed_sql
    assert [params["confidence_1"] for params in db.statement_params] == [0.5, 0.5, 0.5, 0.5]
