import unittest
from datetime import datetime

from app.models.database import CameraPhoto
from app.services.camera_service import (
    build_capture_command,
    build_photo_filename,
    serialize_photo,
)


class CameraServiceTests(unittest.TestCase):
    def test_build_photo_filename_contains_date_and_device(self):
        captured_at = datetime(2026, 5, 18, 14, 30, 15)
        name = build_photo_filename("cat-01", captured_at)
        self.assertTrue(name.endswith(".jpg"))
        self.assertIn("20260518", name)
        self.assertIn("cat-01", name)

    def test_build_photo_filename_sanitizes_mac_style_device_id(self):
        # MAC-style ids contain ':' which is illegal in Windows filenames.
        name = build_photo_filename("aa:bb:cc:dd:ee:ff", datetime(2026, 5, 18, 1, 2, 3))
        self.assertNotIn(":", name)
        self.assertTrue(name.endswith(".jpg"))

    def test_build_photo_filename_is_unique_within_same_second(self):
        captured_at = datetime(2026, 5, 18, 1, 2, 3)
        first = build_photo_filename("cat-01", captured_at, micros=111111)
        second = build_photo_filename("cat-01", captured_at, micros=222222)
        self.assertNotEqual(first, second)

    def test_serialize_photo_builds_public_url(self):
        photo = CameraPhoto(
            id=7,
            device_id="cat-01",
            filename="cat-01_20260518.jpg",
            captured_at=datetime(2026, 5, 18, 14, 30, 15),
        )
        data = serialize_photo(photo)
        self.assertEqual(data["id"], 7)
        self.assertEqual(data["device_id"], "cat-01")
        self.assertEqual(data["url"], "/photos/cat-01_20260518.jpg")
        self.assertEqual(data["captured_at"], "2026-05-18T14:30:15")

    def test_serialize_photo_handles_none(self):
        self.assertIsNone(serialize_photo(None))

    def test_build_capture_command(self):
        cmd = build_capture_command()
        self.assertEqual(cmd["type"], "camera")
        self.assertEqual(cmd["action"], "capture")


if __name__ == "__main__":
    unittest.main()
