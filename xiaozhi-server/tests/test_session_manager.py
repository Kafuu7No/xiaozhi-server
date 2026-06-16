import pytest

from app.services.session_manager import SessionManager


class _FakeWS:
    def __init__(self):
        self.sent = []

    async def send_text(self, text):
        self.sent.append(text)


@pytest.mark.asyncio
async def test_send_to_primary_returns_false_when_no_session():
    sm = SessionManager()
    assert await sm.send_to_primary({"type": "x"}) is False


@pytest.mark.asyncio
async def test_send_to_primary_sends_json_to_first_session():
    sm = SessionManager()
    ws = _FakeWS()
    sm.create_session(ws, "dev", "cli")
    ok = await sm.send_to_primary({"type": "peer_config", "port": 8848})
    assert ok is True
    assert '"type": "peer_config"' in ws.sent[0]
    assert '"port": 8848' in ws.sent[0]
