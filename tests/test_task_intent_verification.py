"""Tests for LLM-based task-intent verification (core/tasks.py)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import tasks


# ── Helper to mock the LLM call ───────────────────────────────────

def _make_mock_llm(response_text: str):
    """Return a callable that mimics _request_openrouter_text."""
    def _mock(system_prompt: str, user_prompt: str, max_tokens: int = 140) -> str:
        return response_text
    return _mock


class TestVerifyTaskIntentLLM:
    # Helper to ensure the API-key check passes for LLM-path tests
    def _set_dummy_key(self, monkeypatch):
        monkeypatch.setattr(tasks, "_OR_KEY", "sk-test-dummy")

    def test_explicit_task_request_high_confidence(self, monkeypatch):
        self._set_dummy_key(monkeypatch)
        monkeypatch.setattr(
            tasks,
            "_request_openrouter_text",
            _make_mock_llm(json.dumps({
                "intent": "explicit_task_request",
                "confidence": 0.92,
                "reason": "User directly asked to create a task"
            })),
        )
        result = tasks.verify_task_intent("Add task call John by 5pm")
        assert result == "Add task call John by 5pm"

    def test_casual_mention_rejected(self, monkeypatch):
        self._set_dummy_key(monkeypatch)
        monkeypatch.setattr(
            tasks,
            "_request_openrouter_text",
            _make_mock_llm(json.dumps({
                "intent": "casual_mention",
                "confidence": 0.95,
                "reason": "User is describing existing tasks, not creating one"
            })),
        )
        result = tasks.verify_task_intent("I have a lot of tasks today")
        assert result is None

    def test_low_confidence_rejected(self, monkeypatch):
        self._set_dummy_key(monkeypatch)
        monkeypatch.setattr(
            tasks,
            "_request_openrouter_text",
            _make_mock_llm(json.dumps({
                "intent": "explicit_task_request",
                "confidence": 0.65,
                "reason": "Ambiguous"
            })),
        )
        result = tasks.verify_task_intent("Something about tasks")
        assert result is None

    def test_missing_api_key_returns_none(self, monkeypatch):
        monkeypatch.setattr(tasks, "_OR_KEY", "")
        result = tasks.verify_task_intent("Add task call John")
        assert result is None

    def test_malformed_json_returns_none(self, monkeypatch):
        self._set_dummy_key(monkeypatch)
        monkeypatch.setattr(
            tasks,
            "_request_openrouter_text",
            _make_mock_llm("not valid json at all"),
        )
        result = tasks.verify_task_intent("Add task call John")
        assert result is None

    def test_empty_llm_response_returns_none(self, monkeypatch):
        self._set_dummy_key(monkeypatch)
        monkeypatch.setattr(
            tasks,
            "_request_openrouter_text",
            _make_mock_llm(""),
        )
        result = tasks.verify_task_intent("Add task call John")
        assert result is None

    def test_json_with_code_fences(self, monkeypatch):
        self._set_dummy_key(monkeypatch)
        monkeypatch.setattr(
            tasks,
            "_request_openrouter_text",
            _make_mock_llm("```json\n" + json.dumps({
                "intent": "explicit_task_request",
                "confidence": 0.88,
                "reason": "Explicit command"
            }) + "\n```"),
        )
        result = tasks.verify_task_intent("Make that a task")
        assert result == "Make that a task"

    def test_unknown_intent_value_returns_none(self, monkeypatch):
        self._set_dummy_key(monkeypatch)
        monkeypatch.setattr(
            tasks,
            "_request_openrouter_text",
            _make_mock_llm(json.dumps({
                "intent": "maybe",
                "confidence": 0.99,
                "reason": "Unclear"
            })),
        )
        result = tasks.verify_task_intent("Add task call John")
        assert result is None

    def test_empty_transcript_returns_none(self, monkeypatch):
        # Should short-circuit before calling LLM
        call_count = [0]
        def _counting_mock(*a, **kw):
            call_count[0] += 1
            return ""
        monkeypatch.setattr(tasks, "_request_openrouter_text", _counting_mock)
        result = tasks.verify_task_intent("")
        assert result is None
        assert call_count[0] == 0

    def test_whitespace_only_transcript_returns_none(self, monkeypatch):
        call_count = [0]
        def _counting_mock(*a, **kw):
            call_count[0] += 1
            return ""
        monkeypatch.setattr(tasks, "_request_openrouter_text", _counting_mock)
        result = tasks.verify_task_intent("   ")
        assert result is None
        assert call_count[0] == 0


class TestEdgeCaseExtraction:
    """Verify extract_task_mention boundary cases from the spec."""

    def test_question_about_tasks_returns_raw(self):
        result = tasks.extract_task_mention("What tasks do I have")
        assert result == "What tasks do I have"
        assert tasks.is_explicit_task_command("What tasks do I have") is False

    def test_past_tense_reflection_returns_raw(self):
        result = tasks.extract_task_mention("I was thinking about tasks earlier")
        assert result == "I was thinking about tasks earlier"
        assert tasks.is_explicit_task_command("I was thinking about tasks earlier") is False

    def test_general_opinion_returns_raw(self):
        result = tasks.extract_task_mention("Tasks are important for productivity")
        assert result == "Tasks are important for productivity"
        assert tasks.is_explicit_task_command("Tasks are important for productivity") is False

    def test_meta_talk_returns_raw(self):
        result = tasks.extract_task_mention("Remind me to think about tasks")
        assert result == "Remind me to think about tasks"
        assert tasks.is_explicit_task_command("Remind me to think about tasks") is False

    def test_task_list_description_returns_raw(self):
        result = tasks.extract_task_mention("My task list is long")
        assert result == "My task list is long"
        assert tasks.is_explicit_task_command("My task list is long") is False

    def test_pure_action_no_task_word_returns_none(self):
        result = tasks.extract_task_mention("Call John")
        assert result is None

    def test_future_intent_no_task_word_returns_none(self):
        result = tasks.extract_task_mention("I will finish the report tomorrow")
        assert result is None

    def test_set_up_a_task_is_explicit(self):
        result = tasks.extract_task_mention("Set up a task for the meeting")
        assert result is not None
        assert tasks.is_explicit_task_command("Set up a task for the meeting") is True

    def test_add_as_a_task_is_explicit(self):
        result = tasks.extract_task_mention("Add call mom as a task")
        assert result is not None
        assert tasks.is_explicit_task_command("Add call mom as a task") is True

    def test_make_that_a_task_is_not_explicit_prefix(self):
        # "make that a task" is handled by _MENTION_PATTERNS which we removed
        # from extract_task_mention, so it should return raw text for LLM
        result = tasks.extract_task_mention("Make that a task")
        assert result == "Make that a task"
        assert tasks.is_explicit_task_command("Make that a task") is False
