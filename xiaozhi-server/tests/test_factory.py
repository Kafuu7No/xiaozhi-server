from app.core.config import get_settings
from app.services.voice import factory
from app.services.voice.llm import DeepSeekLlm, PlaceholderLlm


def _reload_settings(monkeypatch, key: str):
    monkeypatch.setenv("DEEPSEEK_API_KEY", key)
    get_settings.cache_clear()
    factory.reset_providers()


def test_get_llm_falls_back_to_placeholder_without_key(monkeypatch):
    _reload_settings(monkeypatch, "")
    assert isinstance(factory.get_llm(), PlaceholderLlm)


def test_get_llm_uses_deepseek_with_key(monkeypatch):
    _reload_settings(monkeypatch, "sk-test-dummy")
    assert isinstance(factory.get_llm(), DeepSeekLlm)


def test_set_providers_injects_fakes():
    factory.reset_providers()
    sentinel = object()
    factory.set_providers(llm=sentinel)
    assert factory.get_llm() is sentinel
    factory.reset_providers()
