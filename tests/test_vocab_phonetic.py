"""Tests for core/vocab.py phonetic matching and update_correction."""

import os
import importlib
import pathlib

import pytest


@pytest.fixture(autouse=True)
def _isolate_vocab(tmp_path, monkeypatch):
    """Force vocab.json into a throwaway directory and reload module state."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    import core.vocab as vocab
    importlib.reload(vocab)
    vocab._vocab_cache = None  # type: ignore[attr-defined]
    yield vocab
    vocab._vocab_cache = None  # type: ignore[attr-defined]


def test_add_then_phonetic_match_on_similar_spelling(_isolate_vocab):
    vocab = _isolate_vocab
    vocab.add_correction("shivora", "SHIVORA")

    match = vocab.find_phonetic_match("SHEVORA")
    assert match is not None
    assert match["actual"] == "SHIVORA"


def test_update_correction_replaces_entry_and_adds_alias(_isolate_vocab):
    vocab = _isolate_vocab
    vocab.add_correction("shivora", "SHIVORA")

    assert vocab.update_correction("SHIVORA", "SHEVORA") is True

    data = vocab.load_vocab()
    actuals = [e.get("actual") for e in data["corrections"]]
    # No stale SHIVORA entry remains
    assert "SHIVORA" not in actuals
    # New spelling is present
    assert "SHEVORA" in actuals
    # Alias forwards the old heard-form to the new spelling
    heard_to_actual = {e["heard"]: e["actual"] for e in data["corrections"]}
    assert heard_to_actual.get("shivora") == "SHEVORA"
    assert heard_to_actual.get("shevora") == "SHEVORA"


def test_dissimilar_word_is_no_match(_isolate_vocab):
    vocab = _isolate_vocab
    vocab.add_correction("shivora", "SHIVORA")
    assert vocab.find_phonetic_match("KAIROS") is None


def test_apply_corrections_after_update(_isolate_vocab):
    vocab = _isolate_vocab
    vocab.add_correction("shivora", "SHIVORA")
    vocab.update_correction("SHIVORA", "SHEVORA")

    # Both spellings route to SHEVORA in future transcripts
    assert vocab.apply_corrections("check the shivora site") == "check the SHEVORA site"
    assert vocab.apply_corrections("check the shevora site") == "check the SHEVORA site"


def test_exact_match_returns_existing_entry_not_update(_isolate_vocab):
    """find_phonetic_match on the same word returns the entry; caller must
    treat that as 'already present' — nothing to update."""
    vocab = _isolate_vocab
    vocab.add_correction("shivora", "SHIVORA")
    match = vocab.find_phonetic_match("SHIVORA")
    assert match is not None
    assert match["actual"] == "SHIVORA"
