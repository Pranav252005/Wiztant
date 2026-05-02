"""Edge-case tests for dictation junk / hallucination rejection.

These verify that Whisper artifacts, empty transcripts, and common
hallucinations never reach the clipboard or the live preview.
"""

import pytest
from core.hotkeys import _is_dictation_junk, _looks_like_task


class TestIsDictationJunk:
    """Unit tests for the _is_dictation_junk filter."""

    @pytest.mark.parametrize("text", [
        "",
        "   ",
        "\t\n",
        "  \n  ",
    ])
    def test_rejects_empty_and_whitespace(self, text: str):
        """Empty or whitespace-only transcripts are junk."""
        assert _is_dictation_junk(text) is True

    @pytest.mark.parametrize("text", [
        "thank you",
        "Thank You",
        "  thank you  ",
        "thanks",
        "thank",
        "thanks for watching",
        "subtitles by",
        "subtitle by",
        "closed caption",
        "please subscribe",
        "like and subscribe",
        "subscribe now",
    ])
    def test_rejects_common_whisper_hallucinations(self, text: str):
        """Known Whisper hallucination phrases are junk."""
        assert _is_dictation_junk(text) is True

    @pytest.mark.parametrize("text", [
        "so",
        "oh",
        "um",
        "uh",
        "hmm",
        "ok",
        "okay",
        "yeah",
        "yes",
        "no",
        "bye",
        "hi",
        "hello",
        "hey",
        "what",
        "huh",
        "wait",
        "stop",
        "cancel",
    ])
    def test_rejects_single_filler_words(self, text: str):
        """Lone single-token fillers with no context are junk."""
        assert _is_dictation_junk(text) is True

    @pytest.mark.parametrize("text", [
        "call john",
        "hi there",
        "ok let's go",
        "yes please",
        "no thanks",
        "hello world",
        "thank you very much",
        "so what now",
        "oh I see",
        "um maybe",
        "yeah that works",
    ])
    def test_allows_real_multi_word_phrases(self, text: str):
        """Multi-word phrases that contain a filler are still allowed."""
        assert _is_dictation_junk(text) is False

    @pytest.mark.parametrize("text", [
        "Email the team about the deadline",
        "Review PR 42 before lunch",
        "Buy milk and eggs",
        "Remind me to call mom at 5pm",
        "The quick brown fox jumps over the lazy dog",
    ])
    def test_allows_normal_dictation(self, text: str):
        """Normal dictation transcripts are not junk."""
        assert _is_dictation_junk(text) is False

    @pytest.mark.parametrize("text", [
        "a b",
        "x y z",
        "1 2 3",
    ])
    def test_allows_short_letter_sequences(self, text: str):
        """Short letter sequences (e.g. spelled-out words) are allowed."""
        assert _is_dictation_junk(text) is False


class TestLooksLikeTaskVsDictation:
    """Contrast _looks_like_task with _is_dictation_junk expectations."""

    def test_task_is_stricter_than_dictation(self):
        """Task capture rejects things that dictation allows."""
        # Single real word: dictation allows, task rejects
        assert _is_dictation_junk("hello") is True   # single filler
        assert _looks_like_task("hello") is False

        # Two real words: dictation allows, task allows
        assert _is_dictation_junk("call john") is False
        assert _looks_like_task("call john") is True

        # Short filler pair: dictation allows (2 tokens), task rejects
        assert _is_dictation_junk("so oh") is False
        assert _looks_like_task("so oh") is False

    def test_both_reject_empty(self):
        """Both filters reject empty/whitespace."""
        assert _is_dictation_junk("") is True
        assert _looks_like_task("") is False


class TestDictationJunkIntegration:
    """Integration-style tests simulating the full dictation guard."""

    def test_empty_transcript_blocked(self):
        """An empty transcript after Whisper should abort the flow."""
        assert _is_dictation_junk("") is True
        # In hotkeys.py the early `if not text:` check also catches this,
        # so the junk filter is a second line of defense.

    def test_whisper_hallucination_blocked(self):
        """A 'thank you' hallucination should abort before paste."""
        text = "thank you"
        assert _is_dictation_junk(text) is True
        # Would trigger:
        #   [Dictation] Rejected junk/hallucination: 'thank you'
        #   → WS state error + idle

    def test_partial_hallucination_allowed(self):
        """A real sentence containing 'thank you' should NOT be blocked."""
        text = "thank you for the meeting notes"
        assert _is_dictation_junk(text) is False

    def test_gibberish_single_token_blocked(self):
        """A lone 'um' or 'hmm' should abort."""
        assert _is_dictation_junk("um") is True
        assert _is_dictation_junk("hmm") is True

    def test_gibberish_in_context_allowed(self):
        """'um' inside a real sentence should pass."""
        assert _is_dictation_junk("um can you send the report") is False
