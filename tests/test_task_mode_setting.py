"""Tests for task_creation_mode setting loading."""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import hotkeys, tasks


@pytest.fixture(autouse=True)
def _restore_settings_path(monkeypatch):
    """Ensure SETTINGS_PATH is temporarily redirected to a temp file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{}")
        tmp_path = f.name
    original = hotkeys.SETTINGS_PATH
    monkeypatch.setattr(hotkeys, "SETTINGS_PATH", tmp_path)
    yield
    try:
        os.unlink(tmp_path)
    except Exception:
        pass
    monkeypatch.setattr(hotkeys, "SETTINGS_PATH", original)


def test_load_smart_when_set():
    with open(hotkeys.SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump({"task_creation_mode": "smart"}, f)
    assert hotkeys._load_task_creation_mode() == "smart"


def test_load_hotkey_when_set():
    with open(hotkeys.SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump({"task_creation_mode": "hotkey"}, f)
    assert hotkeys._load_task_creation_mode() == "hotkey"


def test_defaults_to_hotkey_when_missing():
    with open(hotkeys.SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump({}, f)
    assert hotkeys._load_task_creation_mode() == "hotkey"


def test_defaults_to_hotkey_when_invalid():
    with open(hotkeys.SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump({"task_creation_mode": "banana"}, f)
    assert hotkeys._load_task_creation_mode() == "hotkey"


class TestSmartModeDecisionTree:
    """Verify the two-layer strict task-detection logic."""

    def test_explicit_prefix_is_fast_path(self):
        text = "add task call John by 5pm"
        candidate = tasks.extract_task_mention(text)
        assert candidate is not None
        assert tasks.is_explicit_task_command(text) is True

    def test_explicit_prefix_this_is_a_task(self):
        text = "this is a task: finish the deck"
        candidate = tasks.extract_task_mention(text)
        assert candidate == "finish the deck"
        assert tasks.is_explicit_task_command(text) is True

    def test_casual_mention_is_not_explicit(self):
        text = "I have a lot of tasks today"
        candidate = tasks.extract_task_mention(text)
        assert candidate == text  # raw text returned for LLM
        assert tasks.is_explicit_task_command(text) is False

    def test_trailing_task_is_not_explicit(self):
        text = "buy groceries this is a task"
        candidate = tasks.extract_task_mention(text)
        assert candidate == text  # raw text returned for LLM
        assert tasks.is_explicit_task_command(text) is False

    def test_normal_dictation_returns_none(self):
        text = "just some normal dictation text"
        candidate = tasks.extract_task_mention(text)
        assert candidate is None

    def test_implicit_natural_language_no_task_word(self):
        text = "I need to call John"
        candidate = tasks.extract_task_mention(text)
        assert candidate is None
        assert tasks.is_explicit_task_command(text) is False

    def test_borderline_mention_llm_accepted(self, monkeypatch):
        text = "Make that a task"
        candidate = tasks.extract_task_mention(text)
        assert candidate == text
        assert tasks.is_explicit_task_command(text) is False
        # Mock LLM to accept
        monkeypatch.setattr(tasks, "_OR_KEY", "sk-test")
        monkeypatch.setattr(
            tasks,
            "_request_openrouter_text",
            lambda *a, **kw: '{"intent": "explicit_task_request", "confidence": 0.9, "reason": "ok"}',
        )
        verified = tasks.verify_task_intent(candidate)
        assert verified == text

    def test_borderline_mention_llm_rejected(self, monkeypatch):
        text = "I have a lot of tasks today"
        candidate = tasks.extract_task_mention(text)
        assert candidate == text
        assert tasks.is_explicit_task_command(text) is False
        # Mock LLM to reject
        monkeypatch.setattr(tasks, "_OR_KEY", "sk-test")
        monkeypatch.setattr(
            tasks,
            "_request_openrouter_text",
            lambda *a, **kw: '{"intent": "casual_mention", "confidence": 0.95, "reason": "no"}',
        )
        verified = tasks.verify_task_intent(candidate)
        assert verified is None
