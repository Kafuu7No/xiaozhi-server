from app.core.config import Settings


def test_voice_settings_have_defaults():
    s = Settings()
    assert s.llm_base_url == "https://token.memoh.net/v1"
    assert s.llm_model == "deepseek-chat"
    assert s.llm_history_turns == 6
    assert s.tts_voice == "zh-CN-XiaoxiaoNeural"
    assert s.stt_provider == "funasr"
    assert isinstance(s.deepseek_api_key, str)
    assert isinstance(s.llm_system_prompt, str) and s.llm_system_prompt
