import pytest
from unittest.mock import AsyncMock

from core.wiztype.config import WizTypeConfig
from core.wiztype.model_manager import ModelManager


def test_wiztype_config_init(tmp_path):
    config = WizTypeConfig(config_file=str(tmp_path / "wiztype_config.json"))
    assert config.enabled is False
    assert config.current_model == "llama3.2:1b"
    assert config.debounce_ms == 350
    assert config.installed_models == []


def test_wiztype_config_load_save(tmp_path):
    config_file = tmp_path / "wiztype_config.json"
    config = WizTypeConfig(config_file=str(config_file))
    config.enabled = True
    config.current_model = "phi3.5"
    config.installed_models = ["phi3.5", "llama3.2:1b"]
    config.save()

    config2 = WizTypeConfig(config_file=str(config_file))
    assert config2.enabled is True
    assert config2.current_model == "phi3.5"
    assert "phi3.5" in config2.installed_models


@pytest.mark.asyncio
async def test_model_manager_init():
    manager = ModelManager()
    assert manager.available_models == ["llama3.2:1b", "phi3.5", "smolvlm"]
    await manager.close()


@pytest.mark.asyncio
async def test_model_manager_pull_model():
    manager = ModelManager()
    manager._ollama_pull = AsyncMock(return_value=True)
    result = await manager.pull_model("llama3.2:1b")
    assert result is True
    manager._ollama_pull.assert_awaited_once_with("llama3.2:1b")
    await manager.close()


@pytest.mark.asyncio
async def test_model_manager_list_installed():
    manager = ModelManager()
    manager._list_installed = AsyncMock(return_value=["llama3.2:1b", "phi3.5"])
    result = await manager.list_installed()
    assert "llama3.2:1b" in result
    assert "phi3.5" in result
    await manager.close()
