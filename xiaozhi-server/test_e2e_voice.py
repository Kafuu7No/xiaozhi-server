# End-to-end voice link test: pretend to be board1 over the device WebSocket.
# Sends real Chinese speech (funasr example wav) as 16kHz STEREO opus frames
# (exactly what board1's encoder produces), then waits for the server's
# auto-stop to fire and a full STT -> LLM -> TTS reply to come back.
import asyncio
import json

import aiohttp
import av

WS_URL = "ws://127.0.0.1:8000/xiaozhi/v1/?token=12345678"
WAV = r"models\paraformer-zh\example\asr_example.wav"


def wav_to_16k_stereo_opus(path: str) -> list[bytes]:
    out = bytearray()
    with av.open(path) as container:
        resampler = av.AudioResampler(format="s16", layout="stereo", rate=16000)
        for frame in container.decode(audio=0):
            for rs in resampler.resample(frame):
                out.extend(rs.to_ndarray().tobytes())
        for rs in resampler.resample(None):
            out.extend(rs.to_ndarray().tobytes())
    pcm = bytes(out)

    codec = av.CodecContext.create("libopus", "w")
    codec.sample_rate = 16000
    codec.layout = "stereo"
    codec.format = "s16"
    samples = 960  # 60ms @ 16k
    bpf = samples * 2 * 2  # stereo s16
    frames = []
    for off in range(0, len(pcm), bpf):
        chunk = pcm[off : off + bpf]
        if len(chunk) < bpf:
            chunk += b"\x00" * (bpf - len(chunk))
        f = av.AudioFrame(format="s16", layout="stereo", samples=samples)
        f.sample_rate = 16000
        f.planes[0].update(chunk)
        for p in codec.encode(f):
            frames.append(bytes(p))
    for p in codec.encode(None):
        frames.append(bytes(p))
    return frames


async def main() -> None:
    frames = wav_to_16k_stereo_opus(WAV)
    print(f"prepared {len(frames)} uplink stereo opus frames")
    got_stt = None
    tts_started = False
    tts_frames = 0
    async with aiohttp.ClientSession() as s:
        async with s.ws_connect(
            WS_URL, headers={"device-id": "te:st:00:00:00:01", "client-id": "e2e-test"}
        ) as ws:
            await ws.send_json({"type": "hello", "version": 1, "transport": "websocket"})
            print("<<", await ws.receive_json())
            await ws.send_json({"type": "listen", "state": "start", "mode": "auto_stop"})
            for f in frames:
                await ws.send_bytes(f)
                await asyncio.sleep(0.01)
            print("frames sent; waiting for auto-stop + reply (up to 90s)...")
            while True:
                msg = await ws.receive(timeout=90)
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    print("<<", data)
                    if data.get("type") == "stt":
                        got_stt = data.get("text", "")
                    if data.get("type") == "tts" and data.get("state") == "start":
                        tts_started = True
                    if data.get("type") == "tts" and data.get("state") == "stop":
                        break
                elif msg.type == aiohttp.WSMsgType.BINARY:
                    tts_frames += 1
                else:
                    print("ws ended:", msg.type)
                    break
    print("=" * 50)
    print(f"STT text  : {got_stt!r}")
    print(f"TTS start : {tts_started}")
    print(f"TTS frames: {tts_frames}")
    ok = bool(got_stt) and tts_started and tts_frames > 0
    print("E2E VOICE LINK:", "PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)


asyncio.run(main())
