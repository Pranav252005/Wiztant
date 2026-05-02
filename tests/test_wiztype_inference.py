import pytest
from unittest.mock import AsyncMock

from core.wiztype.inference import OllamaInference


@pytest.mark.asyncio
async def test_ollama_health_check_true():
    inference = OllamaInference(model="llama3.2:1b")
    inference.client.get = AsyncMock(return_value=type("Resp", (), {"status_code": 200})())
    assert await inference.health_check() is True
    await inference.close()


@pytest.mark.asyncio
async def test_generate_autocorrect_suggestion():
    inference = OllamaInference(model="llama3.2:1b")
    inference.client.post = AsyncMock(
        return_value=type(
            "Resp",
            (),
            {"status_code": 200, "json": lambda self: {"response": "hello"}},
        )()
    )
    suggestion = await inference.suggest_correction(current_word="helo", context="This is a ", max_tokens=2)
    assert suggestion == "hello"
    await inference.close()


@pytest.mark.asyncio
async def test_generate_next_word_suggestion():
    inference = OllamaInference(model="phi3.5")
    inference.client.post = AsyncMock(
        return_value=type(
            "Resp",
            (),
            {"status_code": 200, "json": lambda self: {"response": "lazy\n"}},
        )()
    )
    suggestion = await inference.suggest_next_word(context="The quick brown fox jumps over the ", max_tokens=2)
    assert suggestion == "lazy"
    await inference.close()
