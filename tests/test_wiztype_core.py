import asyncio
from unittest.mock import AsyncMock

import pytest

from core.wiztype import WizType


@pytest.mark.asyncio
async def test_wiztype_init():
    wiztype = WizType()
    try:
        assert wiztype is not None
        assert wiztype.enabled is False
    finally:
        wiztype.shutdown_sync()


@pytest.mark.asyncio
async def test_wiztype_enable():
    wiztype = WizType()
    try:
        wiztype.keyboard_hook.start = lambda: None
        wiztype.enable()
        assert wiztype.enabled is True
    finally:
        wiztype.shutdown_sync()


@pytest.mark.asyncio
async def test_wiztype_disable():
    wiztype = WizType()
    try:
        wiztype.keyboard_hook.stop = lambda: None
        wiztype.enabled = True
        wiztype.disable()
        assert wiztype.enabled is False
    finally:
        wiztype.shutdown_sync()


@pytest.mark.asyncio
async def test_wiztype_keystroke_handler():
    wiztype = WizType()
    try:
        wiztype.enabled = True
        wiztype.config.debounce_ms = 1
        wiztype.inference.suggest_correction = AsyncMock(return_value="world")
        calls = []
        wiztype.overlay.show_suggestion = lambda suggestion: calls.append(suggestion)
        event = {
            "key": "o",
            "is_special": False,
            "current_word": "wurld",
            "context": "Say ",
        }
        await wiztype._handle_keystroke(event)
        await asyncio.sleep(0.02)
        assert calls == ["world"]
    finally:
        wiztype.shutdown_sync()


@pytest.mark.asyncio
async def test_wiztype_suggestion_accepted():
    wiztype = WizType()
    try:
        typed = []
        wiztype.keyboard_controller.type = lambda text: typed.append(text)
        wiztype._suggestion_kind = "next_word"
        wiztype._last_suggestion_event = {"current_word": "", "context": "Hello "}
        wiztype._accept_suggestion("world")
        assert typed == ["world "]
    finally:
        wiztype.shutdown_sync()
