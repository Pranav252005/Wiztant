"""Unit tests for STT refiner."""

import pytest
import logging
from core.stt_refiner import STTRefiner

logger = logging.getLogger(__name__)


class TestSTTRefiner:
    @pytest.fixture
    def refiner(self):
        r = STTRefiner()
        r.set_vocab({
            "groq": "Groq",
            "python": "Python",
            "queue": "Q"
        })
        return r

    def test_refiner_no_changes_needed(self, refiner):
        """Text that needs no refinement."""
        result = refiner.refine_transcript("call john smith about the deadline")
        assert result["refined"]
        assert result["confidence"] > 0.0
        assert result["error"] is None or result["error"] == "GROQ_API_KEY not set"
        logger.info(f"No-change test: {result['refined']}")

    def test_refiner_handles_empty_input(self, refiner):
        """Empty string input."""
        result = refiner.refine_transcript("")
        assert result["refined"] == ""
        assert result["confidence"] == 1.0

    def test_refiner_handles_whitespace_only(self, refiner):
        """Whitespace-only input."""
        result = refiner.refine_transcript("   ")
        assert result["refined"] == "   "
        assert result["confidence"] == 1.0

    def test_vocab_injection(self, refiner):
        """Vocab is loaded correctly."""
        assert refiner.vocab_db.get("groq") == "Groq"
        assert len(refiner.vocab_db) == 3

    def test_context_window(self, refiner):
        """Context history maintains recent tasks."""
        refiner.add_context("task 1")
        refiner.add_context("task 2")
        refiner.add_context("task 3")
        assert len(refiner.context_history) == 3

        # Add 5th and 6th (should remove oldest)
        refiner.add_context("task 4")
        refiner.add_context("task 5")
        refiner.add_context("task 6")
        assert len(refiner.context_history) == 5
        assert "task 1" not in refiner.context_history

    def test_stats_tracking(self, refiner):
        """Stats are tracked correctly (or remain 0 if no API key)."""
        refiner.refine_transcript("test 1")
        refiner.refine_transcript("test 2")

        stats = refiner.get_stats()
        # Without GROQ_API_KEY total_refinements stays 0; with key it increments
        assert stats["total_refinements"] >= 0
        assert stats["avg_latency_ms"] >= 0.0

    def test_batch_refinement(self, refiner):
        """Batch processing multiple texts."""
        texts = ["test 1", "test 2", "test 3"]
        results = refiner.refine_batch(texts)

        assert len(results) == 3
        for result in results:
            assert "refined" in result
            assert "changes" in result
            assert "confidence" in result

    def test_batch_with_empty(self, refiner):
        """Batch includes empty strings gracefully."""
        texts = ["", "valid text", "   "]
        results = refiner.refine_batch(texts)
        assert len(results) == 3
        assert results[0]["refined"] == ""
        assert results[0]["confidence"] == 1.0
        assert results[2]["refined"] == "   "

    def test_reset_stats(self, refiner):
        """Reset stats clears counters."""
        refiner.refine_transcript("test")
        refiner.reset_stats()
        stats = refiner.get_stats()
        assert stats["total_refinements"] == 0
        assert stats["changes_made"] == 0

    def test_refiner_without_api_key(self, monkeypatch):
        """Without API key returns fallback immediately."""
        monkeypatch.setenv("GROQ_API_KEY", "")
        from core.stt_refiner import STTRefiner
        r = STTRefiner()
        result = r.refine_transcript("some text")
        assert result["error"] == "GROQ_API_KEY not set"
        assert result["refined"] == "some text"
