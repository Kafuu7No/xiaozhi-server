import asyncio
import pytest
import time
from fastapi.testclient import TestClient

from app.core.database import async_session
from app.main import app
from app.routers import meow as meow_router
from app.services import meow_service, sensor_service


async def _latest_sensor():
    async with async_session() as db:
        return await sensor_service.get_latest(db)


async def _meow_events():
    async with async_session() as db:
        return await meow_service.get_events(db, hours=24)


async def _meow_stats():
    async with async_session() as db:
        return await meow_service.get_stats(db)


async def _wait_for(predicate, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = await predicate()
        if value:
            return value
        await asyncio.sleep(0.05)
    return await predicate()


@pytest.mark.asyncio
async def test_device_ws_ingests_env_and_meow(db_ready):
    with TestClient(app) as client:
        with client.websocket_connect(
            "/xiaozhi/v1/",
            headers={
                "Authorization": "Bearer 12345678",
                "Device-Id": "test-device",
                "Client-Id": "test-client",
            },
        ) as ws:
            ws.send_json({"type": "hello", "version": 3, "features": {}, "transport": "websocket"})
            hello = ws.receive_json()
            session_id = hello["session_id"]

            ws.send_json(
                {
                    "session_id": session_id,
                    "type": "env",
                    "temp_c": 26.5,
                    "humi_rh": 61.0,
                    "ts": 1234,
                }
            )
            ws.send_json(
                {
                    "session_id": session_id,
                    "type": "meow",
                    "score": 0.91,
                    "is_cat": True,
                    "ts": 1235,
                }
            )

            latest = await _wait_for(_latest_sensor)
            events = await _wait_for(_meow_events)

    assert latest is not None
    assert latest.device_id == "test-device"
    assert latest.temperature == 26.5
    assert latest.humidity == 61.0
    assert len(events) == 1
    assert events[0]["device_id"] == "test-device"
    assert events[0]["score"] == 0.91
    assert events[0]["is_cat"] is True


@pytest.mark.asyncio
async def test_device_ws_drops_low_confidence_meow(db_ready):
    with TestClient(app) as client:
        with client.websocket_connect(
            "/xiaozhi/v1/",
            headers={
                "Authorization": "Bearer 12345678",
                "Device-Id": "low-score-device",
                "Client-Id": "low-score-client",
            },
        ) as ws:
            ws.send_json({"type": "hello", "version": 3, "features": {}, "transport": "websocket"})
            session_id = ws.receive_json()["session_id"]

            ws.send_json(
                {
                    "session_id": session_id,
                    "type": "meow",
                    "score": 0.3,
                    "is_cat": True,
                    "ts": 1235,
                }
            )

            await asyncio.sleep(0.1)
            events = await _meow_events()
            stats = await _meow_stats()

    assert events == []
    assert stats["today_total"] == 0
    assert stats["min_confidence"] == 0.4


@pytest.mark.asyncio
async def test_device_ws_cloud_threshold_overrides_device_meow_flag(db_ready):
    with TestClient(app) as client:
        with client.websocket_connect(
            "/xiaozhi/v1/",
            headers={
                "Authorization": "Bearer 12345678",
                "Device-Id": "threshold-device",
                "Client-Id": "threshold-client",
            },
        ) as ws:
            ws.send_json({"type": "hello", "version": 3, "features": {}, "transport": "websocket"})
            session_id = ws.receive_json()["session_id"]

            ws.send_json(
                {
                    "session_id": session_id,
                    "type": "meow",
                    "score": 0.55,
                    "is_cat": True,
                    "ts": 1235,
                }
            )

            events = await _wait_for(_meow_events)

    assert len(events) == 1
    assert events[0]["score"] == 0.55
    assert events[0]["is_cat"] is False


@pytest.mark.asyncio
async def test_device_ws_accepts_legacy_sensor_payload(db_ready):
    with TestClient(app) as client:
        with client.websocket_connect(
            "/xiaozhi/v1/?token=12345678",
            headers={"Device-Id": "legacy-device", "Client-Id": "legacy-client"},
        ) as ws:
            ws.send_json({"type": "hello", "version": 3, "features": {}, "transport": "websocket"})
            session_id = ws.receive_json()["session_id"]

            ws.send_json(
                {
                    "session_id": session_id,
                    "type": "sensor",
                    "data": {"temperature": "25.2", "humidity": "58.4"},
                }
            )

            latest = await _wait_for(_latest_sensor)

    assert latest is not None
    assert latest.device_id == "legacy-device"
    assert latest.temperature == 25.2
    assert latest.humidity == 58.4


@pytest.mark.asyncio
async def test_device_ws_updates_meow_status(db_ready):
    with TestClient(app) as client:
        with client.websocket_connect(
            "/xiaozhi/v1/?token=12345678",
            headers={"Device-Id": "meow-device", "Client-Id": "meow-client"},
        ) as ws:
            ws.send_json({"type": "hello", "version": 3, "features": {}, "transport": "websocket"})
            session_id = ws.receive_json()["session_id"]

            ws.send_json(
                {
                    "session_id": session_id,
                    "type": "meow_status",
                    "enabled": False,
                    "result": -12,
                    "message": "start_failed",
                    "ts": 1236,
                }
            )

            async def _status_updated():
                status = meow_router.get_meow_control_state()
                if status.get("device_id") == "meow-device" and status.get("message") == "start_failed":
                    return status
                return None

            status = await _wait_for(_status_updated, timeout=1.0)

    assert status["device_id"] == "meow-device"
    assert status["device_enabled"] is False
    assert status["result"] == -12
    assert status["message"] == "start_failed"
