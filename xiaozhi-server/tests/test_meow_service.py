import unittest

from app.services.meow_service import parse_meow_payload


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
        self.assertFalse(parsed["is_cat"])

    def test_infer_is_cat_from_score(self):
        parsed = parse_meow_payload({"data": {"score": 0.92}})
        self.assertIsNotNone(parsed)
        self.assertTrue(parsed["is_cat"])

    def test_keep_confidence_compatibility(self):
        parsed = parse_meow_payload({"confidence": 0.66, "confirmed_detected": 0})
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["score"], 0.66)
        self.assertFalse(parsed["device_is_cat"])
        self.assertFalse(parsed["is_cat"])

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
