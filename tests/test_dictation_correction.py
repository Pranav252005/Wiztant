"""tests/test_dictation_correction.py — Tests for the dictation correction pipeline."""
from __future__ import annotations

import json
import time

import pytest


@pytest.fixture
def tmp_corrections_path(tmp_path, monkeypatch):
    """Redirect dictation_corrections.json to a temp file for hermetic tests."""
    path = tmp_path / "dictation_corrections.json"
    monkeypatch.setattr(
        "core.dictation_correction._CORRECTIONS_PATH",
        path,
    )
    # Reset in-memory index so each test starts fresh
    monkeypatch.setattr("core.dictation_correction._index_built", False)
    monkeypatch.setattr("core.dictation_correction._phonetic_index", {})
    monkeypatch.setattr("core.dictation_correction._UNDO_HOOKS", {})
    yield path


class TestPhoneticKeys:
    def test_phonetic_keys_returns_non_empty(self):
        from core.dictation_correction import phonetic_keys
        dm, sx = phonetic_keys("ethereum")
        assert dm  # Double Metaphone returns non-empty
        assert len(sx) == 4  # Soundex is 4 chars

    def test_soundex_classic_examples(self):
        from core.dictation_correction import _soundex
        # Classic Soundex test cases
        assert _soundex("Robert") == _soundex("Rupert")
        assert len(_soundex("hello")) == 4

    def test_soundex_empty(self):
        from core.dictation_correction import _soundex
        assert _soundex("") == "0000"
        assert _soundex("   ") == "0000"


class TestDomainDetection:
    def test_detect_domain_crypto(self):
        from core.dictation_correction import detect_domain
        assert detect_domain(["buy", "some", "eth"]) == "crypto"

    def test_detect_domain_devops(self):
        from core.dictation_correction import detect_domain
        assert detect_domain(["deploy", "to", "prod"]) == "devops"

    def test_detect_domain_medical(self):
        from core.dictation_correction import detect_domain
        assert detect_domain(["patient", "has", "arrhythmia"]) == "medical"

    def test_detect_domain_none(self):
        from core.dictation_correction import detect_domain
        assert detect_domain(["hello", "world"]) is None

    def test_detect_domain_empty(self):
        from core.dictation_correction import detect_domain
        assert detect_domain([]) is None


class TestRecordAndApply:
    def test_record_correction_stores_entry(self, tmp_corrections_path):
        from core.dictation_correction import record_correction, _load_corrections
        entry = record_correction("ethreum", "ethereum", context_before=["buy", "some", "eth"])
        assert entry
        assert entry["source"] == "ethreum"
        assert entry["target"] == "ethereum"
        assert entry["domain"] == "crypto"
        assert entry["dm_key"]
        assert entry["soundex_key"]

        corrections = _load_corrections()
        assert len(corrections) == 1

    def test_apply_corrections_auto_replace(self, tmp_corrections_path):
        from core.dictation_correction import record_correction, apply_corrections
        record_correction("ethreum", "ethereum", context_before=["buy", "some"])
        corrected, changes = apply_corrections("buy some ethreum")
        assert "ethereum" in corrected
        assert any("ethreum->ethereum" in c for c in changes)

    def test_apply_corrections_no_match(self, tmp_corrections_path):
        from core.dictation_correction import apply_corrections
        corrected, changes = apply_corrections("hello world")
        assert corrected == "hello world"
        assert changes == []

    def test_apply_corrections_respects_domain(self, tmp_corrections_path):
        from core.dictation_correction import record_correction, apply_corrections
        # "gitt" in devops context -> "git"
        record_correction("gitt", "git", context_before=["deploy", "to"], domain="devops")
        corrected, _ = apply_corrections("deploy to gitt", context_window=["deploy", "to"])
        assert "git" in corrected

    def test_record_updates_existing_same_source(self, tmp_corrections_path):
        from core.dictation_correction import record_correction, _load_corrections
        record_correction("ethreum", "ethereum")
        record_correction("ethreum", "ethereum")
        corrections = _load_corrections()
        assert len(corrections) == 1
        assert corrections[0]["frequency"] == 2

    def test_record_ignores_identical_source_target(self, tmp_corrections_path):
        from core.dictation_correction import record_correction, _load_corrections
        record_correction("hello", "hello")
        corrections = _load_corrections()
        assert len(corrections) == 0

    def test_apply_below_confidence_ignored(self, tmp_corrections_path):
        from core.dictation_correction import record_correction, apply_corrections
        record_correction("ethreum", "ethereum", confidence=0.3)
        corrected, changes = apply_corrections("buy some ethreum", min_confidence=0.7)
        assert "ethreum" in corrected  # Not replaced because confidence too low
        assert changes == []


class TestUndoHook:
    def test_undo_hook_finalize_stores_correction(self, tmp_corrections_path, monkeypatch):
        from core.dictation_correction import (
            start_undo_hook,
            on_preview_edit,
            _finalize_hook,
            _load_corrections,
        )
        start_undo_hook("sess-1", "buy some ethreum", "buy some ethreum")
        on_preview_edit("sess-1", "buy some ethereum")
        _finalize_hook("sess-1")
        corrections = _load_corrections()
        assert any(
            c["source"] == "ethreum" and c["target"] == "ethereum"
            for c in corrections
        )

    def test_undo_hook_ignores_unchanged(self, tmp_corrections_path):
        from core.dictation_correction import (
            start_undo_hook,
            _finalize_hook,
            _load_corrections,
        )
        start_undo_hook("sess-2", "hello world", "hello world")
        _finalize_hook("sess-2")
        corrections = _load_corrections()
        assert len(corrections) == 0

    def test_undo_hook_close_finalizes(self, tmp_corrections_path):
        from core.dictation_correction import (
            start_undo_hook,
            on_preview_edit,
            on_preview_close,
            _load_corrections,
        )
        start_undo_hook("sess-3", "bitcon", "bitcon")
        on_preview_edit("sess-3", "bitcoin")
        on_preview_close("sess-3")
        corrections = _load_corrections()
        assert any(c["source"] == "bitcon" and c["target"] == "bitcoin" for c in corrections)

    def test_undo_hook_copy_extends_timer(self, tmp_corrections_path, monkeypatch):
        from core.dictation_correction import (
            start_undo_hook,
            on_preview_copy,
            _UNDO_HOOKS,
        )
        # Set a short copy wait for testing
        monkeypatch.setattr("core.dictation_correction._load_copy_wait_sec", lambda: 1)
        start_undo_hook("sess-4", "test", "test")
        on_preview_copy("sess-4")
        hook = _UNDO_HOOKS.get("sess-4")
        assert hook["copied"] is True
        assert hook["copy_at"] > 0

    def test_undo_hook_optimize_tracked(self, tmp_corrections_path):
        from core.dictation_correction import (
            start_undo_hook,
            on_preview_optimize,
            _finalize_hook,
            _load_corrections,
        )
        start_undo_hook("sess-5", "write code", "write code")
        on_preview_optimize("sess-5", "write elegant code")
        _finalize_hook("sess-5")
        corrections = _load_corrections()
        assert any(c["source"] == "write code" for c in corrections)


class TestStats:
    def test_get_correction_stats_empty(self, tmp_corrections_path):
        from core.dictation_correction import get_correction_stats
        stats = get_correction_stats()
        assert stats["total_corrections"] == 0

    def test_get_correction_stats_with_data(self, tmp_corrections_path):
        from core.dictation_correction import record_correction, get_correction_stats
        record_correction("ethreum", "ethereum", domain="crypto")
        record_correction("gitt", "git", domain="devops")
        stats = get_correction_stats()
        assert stats["total_corrections"] == 2
        assert stats["domain_breakdown"]["crypto"] == 1
        assert stats["domain_breakdown"]["devops"] == 1
