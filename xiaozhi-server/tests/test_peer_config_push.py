import pytest
from fastapi.testclient import TestClient

from app.core.database import async_session
from app import main as main_module
from app.main import app
from app.services import settings_service
from app.services.session_manager import session_manager


async def _noop_runner():
    return None


def _disable_background_schedule_runner(monkeypatch):
    monkeypatch.setattr(main_module.schedule_runner, "start", _noop_runner)
    monkeypatch.setattr(main_module.schedule_runner, "stop", _noop_runner)


@pytest.mark.asyncio
async def test_board1_receives_peer_config_after_hello(db_ready, monkeypatch):
    session_manager._sessions.clear()
    _disable_background_schedule_runner(monkeypatch)

    async with async_session() as db:
        await settings_service.save_settings(
            db, {"autoOnMeow": True, "delaySeconds": 9}
        )

    with TestClient(app) as client:
        with client.websocket_connect(
            "/xiaozhi/v1/?token=12345678",
            headers={"Device-Id": "pc-board1", "Client-Id": "pc-client"},
        ) as ws:
            ws.send_json(
                {
                    "type": "hello",
                    "version": 3,
                    "features": {},
                    "transport": "websocket",
                }
            )
            ws.receive_json()
            msg = ws.receive_json()

    assert msg["type"] == "peer_config"
    assert msg["autoOnMeow"] is True
    assert msg["delaySeconds"] == 9
    assert isinstance(msg["board2_ips"], list)
    assert msg["port"] == 8848


@pytest.mark.asyncio
async def test_board1_receives_peer_config_after_water_settings_update(db_ready, monkeypatch):
    session_manager._sessions.clear()
    _disable_background_schedule_runner(monkeypatch)

    with TestClient(app) as client:
        with client.websocket_connect(
            "/xiaozhi/v1/?token=12345678",
            headers={"Device-Id": "pc-board1", "Client-Id": "pc-client"},
        ) as ws:
            ws.send_json(
                {
                    "type": "hello",
                    "version": 3,
                    "features": {},
                    "transport": "websocket",
                }
            )
            ws.receive_json()
            ws.receive_json()

            resp = client.put(
                "/api/water/settings",
                json={"autoOnMeow": True, "delaySeconds": 7},
            )
            assert resp.status_code == 200
            msg = ws.receive_json()

    assert msg["type"] == "peer_config"
    assert msg["autoOnMeow"] is True
    assert msg["delaySeconds"] == 7


@pytest.mark.asyncio
async def test_schedule_runner_periodically_pushes_peer_config(db_ready, monkeypatch):
    from app.services import schedule_runner as schedule_module

    calls = []

    async def fake_push_peer_config(db):
        calls.append(db)
        return True

    runner = schedule_module.ScheduleRunner()
    monkeypatch.setattr(
        schedule_module.peer_config_service, "push_peer_config", fake_push_peer_config
    )

    await runner._maybe_push_peer_config()
    await runner._maybe_push_peer_config()
    assert len(calls) == 1

    runner._last_peer_push -= schedule_module.PEER_CONFIG_INTERVAL_S + 1
    await runner._maybe_push_peer_config()
    assert len(calls) == 2
