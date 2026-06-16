import unittest
from datetime import datetime

from app.models.database import WaterRecord, WaterSchedule
from app.services.water_service import (
    build_pump_command,
    estimate_volume_ml,
    serialize_record,
    serialize_schedule,
)


class WaterServiceTests(unittest.TestCase):
    def test_estimate_volume_ml(self):
        self.assertEqual(estimate_volume_ml(15), 45)
        self.assertEqual(estimate_volume_ml(0), 0)

    def test_serialize_record(self):
        rec = WaterRecord(
            id=3,
            device_id="cat-01",
            trigger_type="manual",
            duration_seconds=20,
            started_at=datetime(2026, 5, 19, 8, 0, 0),
            ended_at=datetime(2026, 5, 19, 8, 0, 20),
        )
        data = serialize_record(rec)
        self.assertEqual(data["id"], 3)
        self.assertEqual(data["trigger_type"], "manual")
        self.assertEqual(data["duration_seconds"], 20)
        self.assertEqual(data["volume_ml"], 60)
        self.assertEqual(data["started_at"], "2026-05-19T08:00:00")
        self.assertEqual(data["ended_at"], "2026-05-19T08:00:20")

    def test_serialize_record_handles_null_ended_at(self):
        rec = WaterRecord(
            id=4,
            device_id="cat-01",
            trigger_type="schedule",
            duration_seconds=10,
            started_at=datetime(2026, 5, 19, 8, 0, 0),
            ended_at=None,
        )
        self.assertIsNone(serialize_record(rec)["ended_at"])

    def test_serialize_schedule(self):
        sched = WaterSchedule(
            id=1, label="早晨补水", time="08:30", duration_seconds=15, enabled=True
        )
        data = serialize_schedule(sched)
        self.assertEqual(data["id"], 1)
        self.assertEqual(data["label"], "早晨补水")
        self.assertEqual(data["time"], "08:30")
        self.assertEqual(data["duration_seconds"], 15)
        self.assertTrue(data["enabled"])

    def test_build_pump_command_start_includes_duration(self):
        cmd = build_pump_command("start", duration=15)
        self.assertEqual(cmd["type"], "water_pump")
        self.assertEqual(cmd["action"], "start")
        self.assertEqual(cmd["duration"], 15)

    def test_build_pump_command_stop_omits_duration(self):
        cmd = build_pump_command("stop")
        self.assertEqual(cmd["type"], "water_pump")
        self.assertEqual(cmd["action"], "stop")
        self.assertNotIn("duration", cmd)


if __name__ == "__main__":
    unittest.main()
