"""Manual smoke test for FunASR.

Prepare a 16kHz mono WAV file and run:
    python tests/smoke_stt.py path/to/speech.wav
"""

import asyncio
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.voice.stt import FunAsrStt


def read_wav_pcm(path: str) -> bytes:
    with wave.open(path, "rb") as wav:
        assert wav.getframerate() == 16000, "wav must be 16kHz"
        assert wav.getnchannels() == 1, "wav must be mono"
        return wav.readframes(wav.getnframes())


async def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python tests/smoke_stt.py path/to/speech.wav")
        return
    pcm = read_wav_pcm(sys.argv[1])
    stt = FunAsrStt()
    text = await stt.transcribe(pcm)
    print("识别结果:", repr(text))


if __name__ == "__main__":
    asyncio.run(main())
