"""Manual smoke test for EdgeTTS. Usage: python tests/smoke_tts.py"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.services.voice.tts import EdgeTts


async def main() -> None:
    s = get_settings()
    tts = EdgeTts(s.tts_voice)
    audio = await tts.synthesize("你好，我是智能猫窝助手。")
    out = Path(__file__).resolve().parent / "smoke_tts_output.mp3"
    out.write_bytes(audio)
    print(f"合成 {len(audio)} 字节，已写入 {out}")
    assert len(audio) > 1000, "音频过小，疑似失败"


if __name__ == "__main__":
    asyncio.run(main())
