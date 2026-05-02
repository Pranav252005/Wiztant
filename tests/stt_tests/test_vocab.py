"""Unit tests for vocabulary manager."""

import pytest
import os
from core.vocab import VocabManager


class TestVocabManager:
    @pytest.fixture
    def vocab(self, tmp_path):
        """Vocab manager with temp storage."""
        manager = VocabManager()
        manager.vocab_path = str(tmp_path / "vocab_test.json")
        manager.vocab_db = {}
        return manager

    def test_add_correction(self, vocab):
        """Add vocabulary correction."""
        vocab.add_correction("groq", "Groq")
        assert vocab.vocab_db.get("groq") == "Groq"

    def test_apply_corrections_basic(self, vocab):
        """Apply vocab corrections."""
        vocab.vocab_db["groq"] = "Groq"

        corrected, changes = vocab.apply_corrections("use groq for this")
        assert "Groq" in corrected
        assert "groq->Groq" in changes

    def test_apply_corrections_multiple(self, vocab):
        """Apply multiple corrections."""
        vocab.vocab_db["groq"] = "Groq"
        vocab.vocab_db["python"] = "Python"

        corrected, changes = vocab.apply_corrections("use groq and python")
        assert "Groq" in corrected
        assert "Python" in corrected
        assert len(changes) == 2

    def test_apply_corrections_surgical(self, vocab):
        """Surgical: only flagged words changed."""
        vocab.vocab_db["groq"] = "Groq"

        # "grow" should NOT be changed (not exact match)
        corrected, changes = vocab.apply_corrections("grow the project with groq")
        assert corrected == "grow the project with Groq"
        assert len(changes) == 1

    def test_apply_corrections_case_insensitive(self, vocab):
        """Case-insensitive matching."""
        vocab.vocab_db["groq"] = "Groq"

        corrected, _ = vocab.apply_corrections("Use GROQ and Groq")
        assert corrected.count("Groq") == 2

    def test_apply_corrections_no_match(self, vocab):
        """No corrections applied when vocab empty."""
        corrected, changes = vocab.apply_corrections("plain text here")
        assert corrected == "plain text here"
        assert changes == []

    def test_vocab_stats(self, vocab):
        """Get vocabulary statistics."""
        vocab.vocab_db["a"] = "A"
        vocab.vocab_db["b"] = "B"

        stats = vocab.get_vocab_stats()
        assert stats["total_corrections"] == 2
        assert len(stats["corrections"]) == 2

    def test_clear_vocab(self, vocab):
        """Clear all vocabulary."""
        vocab.vocab_db["test"] = "Test"
        vocab.clear_vocab()

        assert len(vocab.vocab_db) == 0
