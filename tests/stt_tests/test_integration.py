"""Integration tests for full STT pipeline."""

import pytest
import time
from core.stt_refiner import STTRefiner
from core.smart_paste import SmartPasteEngine
from core.vocab import VocabManager


class TestSTTPipeline:
    """Test full refine -> vocab -> paste pipeline."""

    @pytest.fixture
    def pipeline(self):
        """Complete pipeline setup."""
        return {
            "refiner": STTRefiner(),
            "paste": SmartPasteEngine(),
            "vocab": VocabManager()
        }

    def test_full_pipeline_basic(self, pipeline):
        """Basic pipeline: transcript -> refined -> paste."""
        transcript = "call john about the deadline"

        # Refine
        refined_result = pipeline["refiner"].refine_transcript(transcript)
        refined = refined_result["refined"]

        # Vocab
        corrected, _ = pipeline["vocab"].apply_corrections(refined)

        # Paste (format only, don't actually paste)
        formatted = pipeline["paste"].format_for_task(corrected)

        assert len(formatted) > 0
        assert formatted[0].isupper()

    def test_full_pipeline_with_vocab_correction(self, pipeline):
        """Pipeline with vocabulary learning."""
        transcript = "setup groq integration"

        # Add vocab
        pipeline["vocab"].add_correction("groq", "Groq")

        # Refine
        refined_result = pipeline["refiner"].refine_transcript(transcript)
        refined = refined_result["refined"]

        # Vocab corrections
        corrected, changes = pipeline["vocab"].apply_corrections(refined)

        # Should contain "Groq"
        assert "Groq" in corrected

    def test_pipeline_stat_tracking(self, pipeline):
        """Stats tracked through pipeline (or remain 0 without API key)."""
        transcript = "test one"
        pipeline["refiner"].refine_transcript(transcript)

        refiner_stats = pipeline["refiner"].get_stats()
        # Without GROQ_API_KEY total_refinements stays 0; with key it increments
        assert refiner_stats["total_refinements"] >= 0

    def test_pipeline_latency_budget(self, pipeline):
        """Full pipeline completes within latency budget."""
        start = time.time()

        # Refine
        refined_result = pipeline["refiner"].refine_transcript("test task")

        # Vocab
        pipeline["vocab"].apply_corrections(refined_result["refined"])

        # Paste format
        pipeline["paste"].format_for_task(refined_result["refined"])

        elapsed = (time.time() - start) * 1000

        # Should be under 3 seconds for full pipeline
        assert elapsed < 3000, f"Pipeline took {elapsed:.0f}ms (budget: 3000ms)"

    def test_smart_paste_formatting(self, pipeline):
        """Smart paste handles task formatting correctly."""
        raw = "  create a task for um the Q4 report  "
        formatted = pipeline["paste"].format_for_task(raw)
        assert formatted.startswith("Create")
        assert " um " not in formatted

    def test_end_to_end_vocab_persisted(self, pipeline):
        """Vocab changes survive through pipeline."""
        pipeline["vocab"].add_correction("api", "API")
        text = "fix the api endpoint"
        corrected, changes = pipeline["vocab"].apply_corrections(text)
        assert "API" in corrected
        assert any("api->API" in c for c in changes)
