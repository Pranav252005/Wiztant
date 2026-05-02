"""Extended edge-case tests for core/task_classifier.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from core import task_classifier


class TestStripSubject:
    def test_empty_subject_returns_original(self):
        assert task_classifier._strip_subject("hello world", "") == "hello world"

    def test_subject_at_start(self):
        result = task_classifier._strip_subject("SHIVORA landing page due 6 pm", "SHIVORA")
        assert "SHIVORA" not in result
        assert "due 6 pm" in result

    def test_subject_at_end(self):
        result = task_classifier._strip_subject("due 6 pm for SHIVORA", "SHIVORA")
        assert "SHIVORA" not in result
        assert "due 6 pm" in result

    def test_subject_in_middle(self):
        result = task_classifier._strip_subject("Build the SHIVORA site today", "SHIVORA")
        assert "SHIVORA" not in result
        assert "Build the site today" == result

    def test_case_insensitive(self):
        result = task_classifier._strip_subject("shivora landing page", "SHIVORA")
        assert "shivora" not in result.lower()

    def test_stripped_becomes_empty_returns_original(self):
        # If stripping removes everything, return original
        result = task_classifier._strip_subject("SHIVORA", "SHIVORA")
        assert result == "SHIVORA"


class TestSharedSubject:
    def test_no_proper_nouns(self):
        result = task_classifier._shared_subject("go to the store", "buy some milk")
        assert result is None

    def test_all_stopwords(self):
        result = task_classifier._shared_subject("the and or", "for in on")
        assert result is None

    def test_single_shared_proper_noun(self):
        result = task_classifier._shared_subject("Build SHIVORA page", "SHIVORA deployment")
        assert result == "shivora"

    def test_multiple_shared_prefers_longest(self):
        result = task_classifier._shared_subject("Build SHIVORA landing page", "SHIVORA landing page review")
        assert result == "shivora"  # longest by char count, not necessarily best

    def test_domain_shared(self):
        result = task_classifier._shared_subject("fix api.example.com bug", "deploy api.example.com")
        assert result is not None
        assert "example.com" in result


class TestNormalize:
    def test_whitespace_collapsed(self):
        result = task_classifier._normalize("  hello   world  ")
        assert result == "hello world"

    def test_lowercased(self):
        result = task_classifier._normalize("Hello World")
        assert result == "hello world"

    def test_punctuation_stripped(self):
        result = task_classifier._normalize("hello, world.")
        assert result == "hello, world"  # trailing . stripped by strip(" ,.-:;")

    def test_ends_stripped(self):
        result = task_classifier._normalize(" ,hello world, ")
        assert result == "hello world"


class TestSubjectTokens:
    def test_extracts_uppercase(self):
        tokens = task_classifier._subject_tokens("Build SHIVORA landing page")
        assert "shivora" in tokens

    def test_extracts_mixed_case(self):
        tokens = task_classifier._subject_tokens("Update GitHubActions workflow")
        assert "githubactions" in tokens

    def test_extracts_domain(self):
        tokens = task_classifier._subject_tokens("Fix api.example.com bug")
        assert "api.example.com" in tokens

    def test_skips_stopwords(self):
        tokens = task_classifier._subject_tokens("The and or for")
        assert len(tokens) == 0

    def test_skips_short_tokens(self):
        tokens = task_classifier._subject_tokens("Go to XY")
        # "XY" is length 2, skipped; "Go" is length 2, also skipped
        assert "xy" not in tokens

    def test_extracts_hyphenated(self):
        tokens = task_classifier._subject_tokens("Use auto-complete feature")
        assert "auto-complete" in tokens

    def test_all_lower_no_punctuation_no_tokens(self):
        tokens = task_classifier._subject_tokens("go to the store and buy milk")
        # nothing uppercase, no dots, no hyphens
        assert len(tokens) == 0


class TestLlmArbitrateEdgeCases:
    def test_no_api_key_returns_none(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "")
        monkeypatch.setattr(task_classifier, "_request_openrouter_text", None)
        result = task_classifier._llm_arbitrate("a", "b")
        assert result is None

    def test_none_request_openrouter_text_returns_none(self, monkeypatch):
        monkeypatch.setattr(task_classifier, "_request_openrouter_text", None)
        result = task_classifier._llm_arbitrate("a", "b")
        assert result is None

    def test_malformed_json_returns_none(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.setattr(
            task_classifier,
            "_request_openrouter_text",
            lambda *a, **kw: "not json at all",
        )
        result = task_classifier._llm_arbitrate("a", "b")
        assert result is None

    def test_valid_response_parsed(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.setattr(
            task_classifier,
            "_request_openrouter_text",
            lambda *a, **kw: '{"relation": "duplicate", "reason": "same"}',
        )
        result = task_classifier._llm_arbitrate("a", "b")
        assert result == {"relation": "duplicate", "reason": "same"}

    def test_invalid_relation_returns_none(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.setattr(
            task_classifier,
            "_request_openrouter_text",
            lambda *a, **kw: '{"relation": "maybe", "reason": "unclear"}',
        )
        result = task_classifier._llm_arbitrate("a", "b")
        assert result is None

    def test_code_fence_stripped(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.setattr(
            task_classifier,
            "_request_openrouter_text",
            lambda *a, **kw: '```json\n{"relation": "subtask", "reason": "nested"}\n```',
        )
        result = task_classifier._llm_arbitrate("a", "b")
        assert result == {"relation": "subtask", "reason": "nested"}


class TestClassifyEdgeCases:
    def test_empty_candidate_is_new(self):
        result = task_classifier.classify("", [])
        assert result["action"] == "new"

    def test_none_existing_returns_new(self):
        result = task_classifier.classify("hello", None)
        assert result["action"] == "new"

    def test_done_tasks_ignored_for_duplicate(self):
        existing = [{"id": "t1", "text": "Build SHIVORA", "status": "done"}]
        result = task_classifier.classify("Build SHIVORA", existing)
        assert result["action"] == "new"

    def test_subtask_text_strips_subject(self, monkeypatch):
        monkeypatch.setattr(task_classifier, "_llm_arbitrate", lambda *a, **kw: None)
        existing = [{"id": "t1", "text": "Build SHIVORA landing page", "status": "pending"}]
        result = task_classifier.classify("SHIVORA landing page due 6 pm", existing)
        assert result["action"] == "subtask"
        assert "due 6 pm" in result["subtask_text"].lower()
