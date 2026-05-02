from unittest.mock import Mock

from core.wiztype.keyboard_hook import KeyboardHook


def test_keyboard_hook_initialization():
    hook = KeyboardHook()
    assert hook is not None
    assert hook.enabled is False


def test_register_callback():
    hook = KeyboardHook()
    callback = Mock()
    hook.register_callback(callback)
    assert callback in hook.callbacks


def test_deregister_callback():
    hook = KeyboardHook()
    callback = Mock()
    hook.register_callback(callback)
    hook.deregister_callback(callback)
    assert callback not in hook.callbacks


def test_keystroke_event_structure():
    hook = KeyboardHook()
    event = hook._create_event(key="a", is_special=False)
    assert event["key"] == "a"
    assert event["is_special"] is False
    assert "timestamp" in event


def test_word_state_updates():
    hook = KeyboardHook()
    hook._update_word_state("h", False)
    hook._update_word_state("i", False)
    hook._update_word_state("space", True)
    assert hook._current_word == ""
    assert hook._context == "hi "
