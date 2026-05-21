"""Tests for Groq STT retry logic."""

from unittest.mock import patch, MagicMock

import pytest

from core.stt_engine import _transcribe_groq_with_prompt


class TestGroqRetry:
    """Verify exponential backoff retry on transient Groq errors."""

    def test_retries_on_rate_limit(self):
        """Should retry and succeed on transient 429 errors."""
        mock_client = MagicMock()
        # First 2 calls raise 429, 3rd succeeds
        side_effects = [
            Exception("Rate limit exceeded"),
            Exception("Rate limit exceeded"),
            MagicMock(text="hello world"),
        ]
        mock_client.audio.transcriptions.create.side_effect = side_effects

        with patch("core.voice._get_groq_client", return_value=mock_client):
            with patch("core.stt_engine.time.sleep", return_value=None):  # speed up test
                result = _transcribe_groq_with_prompt(b"fake_audio", "")

        assert result == "hello world"
        assert mock_client.audio.transcriptions.create.call_count == 3

    def test_fails_after_max_retries(self):
        """Should raise after exhausting retries on transient errors."""
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.side_effect = Exception(
            "timeout"
        )

        with patch("core.voice._get_groq_client", return_value=mock_client):
            with patch("core.stt_engine.time.sleep", return_value=None):
                with pytest.raises(Exception, match="timeout"):
                    _transcribe_groq_with_prompt(b"fake_audio", "")

        # initial + 3 retries
        assert mock_client.audio.transcriptions.create.call_count == 4

    def test_no_retry_on_non_transient_error(self):
        """Should not retry on non-transient errors like auth failures."""
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.side_effect = Exception(
            "Invalid API key"
        )

        with patch("core.voice._get_groq_client", return_value=mock_client):
            with patch("core.stt_engine.time.sleep", return_value=None):
                with pytest.raises(Exception, match="Invalid API key"):
                    _transcribe_groq_with_prompt(b"fake_audio", "")

        # Only 1 attempt — no retries for non-transient errors
        assert mock_client.audio.transcriptions.create.call_count == 1
