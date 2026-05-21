"""Tests for StreamingSTT VAD auto-stop and max duration."""

import time
from unittest.mock import patch

import core as state
import pytest

from core.stt_engine import StreamingSTT


class TestVADAutoStop:
    """Verify silence-based auto-stop and max duration cap."""

    def test_silence_auto_stop(self):
        """Recording should auto-stop after silence_sec of low audio_level."""
        stt = StreamingSTT(silence_sec=0.3, max_sec=300)
        stt.start()
        assert stt.is_recording()

        # Simulate 500 ms of silence (below 300 threshold)
        with patch.object(state, "audio_level", 50.0):
            # Poll instead of blind sleep to avoid flakiness in CI
            for _ in range(30):
                if not stt.is_recording():
                    break
                time.sleep(0.05)

        assert not stt.is_recording(), "Expected auto-stop after silence"

    def test_max_duration_auto_stop(self):
        """Recording should auto-stop after max_sec."""
        stt = StreamingSTT(silence_sec=999, max_sec=0.2)
        stt.start()
        assert stt.is_recording()

        for _ in range(30):
            if not stt.is_recording():
                break
            time.sleep(0.05)

        assert not stt.is_recording(), "Expected auto-stop after max_sec"

    def test_speech_resets_silence_timer(self):
        """Intermittent speech should reset silence timer."""
        stt = StreamingSTT(silence_sec=0.8, max_sec=300)
        stt.start()
        assert stt.is_recording()

        # 0.3s silence + 0.05s speech + 0.3s silence = 0.65s total silence < 0.8s
        with patch.object(state, "audio_level", 50.0):
            time.sleep(0.3)
            with patch.object(state, "audio_level", 500.0):
                time.sleep(0.05)
            time.sleep(0.3)

        assert stt.is_recording(), "Speech blip should reset silence timer"
        stt.request_stop()
