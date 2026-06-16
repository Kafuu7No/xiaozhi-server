from fastapi.testclient import TestClient

from app.main import app
from app.services.voice import factory


class FakeStt:
    async def transcribe(self, pcm):
        return "测试语音"


class FakeLlm:
    async def chat(self, system_prompt, history, user_text):
        return "你好呀"


class FakeTts:
    async def synthesize(self, text):
        return b"FAKE_MP3_BYTES"


def test_ws_voice_full_turn(db_ready):
    factory.set_providers(stt=FakeStt(), llm=FakeLlm(), tts=FakeTts())
    client = TestClient(app)
    with client.websocket_connect("/ws/voice") as ws:
        ws.send_json({"type": "start"})
        ws.send_bytes(b"\x01\x02" * 800)
        ws.send_json({"type": "stop"})

        stt_msg = ws.receive_json()
        reply_msg = ws.receive_json()
        audio_hdr = ws.receive_json()
        audio_bin = ws.receive_bytes()

    assert stt_msg == {"type": "stt", "text": "测试语音"}
    assert reply_msg == {"type": "reply", "text": "你好呀"}
    assert audio_hdr == {"type": "tts_audio"}
    assert audio_bin == b"FAKE_MP3_BYTES"
    factory.reset_providers()
