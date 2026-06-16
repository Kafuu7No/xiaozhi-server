"""LLM providers: abstract base, placeholder fallback, and DeepSeek."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger("xz.voice.llm")


class LlmProvider(ABC):
    """Conversation model interface."""

    @abstractmethod
    async def chat(
        self, system_prompt: str, history: list[dict], user_text: str
    ) -> str:
        """Return the assistant reply for the current user text."""


class PlaceholderLlm(LlmProvider):
    """Fallback implementation used when no API key is configured."""

    async def chat(
        self, system_prompt: str, history: list[dict], user_text: str
    ) -> str:
        return f"我听到你说：{user_text}"


class DeepSeekLlm(LlmProvider):
    """DeepSeek implementation through the OpenAI-compatible API."""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=15.0)
        self._model = model

    async def chat(
        self, system_prompt: str, history: list[dict], user_text: str
    ) -> str:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_text})
        try:
            resp = await self._client.chat.completions.create(
                model=self._model, messages=messages
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as exc:
            logger.error("LLM request failed: %s", exc)
            return "我现在有点忙，待会儿再聊。"
