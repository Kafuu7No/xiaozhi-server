"""Manual smoke test for DeepSeek/placeholder LLM. Usage: python tests/smoke_llm.py"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.services.voice.llm import DeepSeekLlm, PlaceholderLlm


async def main() -> None:
    s = get_settings()
    if not s.deepseek_api_key:
        print("DEEPSEEK_API_KEY is not configured; testing PlaceholderLlm")
        llm = PlaceholderLlm()
    else:
        llm = DeepSeekLlm(s.deepseek_api_key, s.llm_base_url, s.llm_model)
    reply = await llm.chat(s.llm_system_prompt, [], "你好，你是谁？")
    print("回复:", reply)


if __name__ == "__main__":
    asyncio.run(main())
