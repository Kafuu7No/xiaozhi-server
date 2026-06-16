from app.services.voice.llm import LlmProvider, PlaceholderLlm


async def test_placeholder_echoes_user_text():
    llm = PlaceholderLlm()
    reply = await llm.chat("system", [], "今天天气怎么样")
    assert "今天天气怎么样" in reply


async def test_placeholder_is_an_llm_provider():
    assert isinstance(PlaceholderLlm(), LlmProvider)
