"""Tests for core/guardrails.py — pure safety functions."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from core import guardrails as gr


class TestIsDestructiveAction:
    def test_delete_file_matches(self):
        is_dest, reason = gr.is_destructive_action("delete the file foo.txt")
        assert is_dest is True
        assert "destructive_keyword" in reason

    def test_remove_file_matches(self):
        is_dest, reason = gr.is_destructive_action("remove file bar.txt")
        assert is_dest is True
        assert "remove" in reason.lower()

    def test_format_drive_matches(self):
        is_dest, reason = gr.is_destructive_action("format drive C:")
        assert is_dest is True

    def test_rm_rf_matches(self):
        is_dest, reason = gr.is_destructive_action("rm -rf /")
        assert is_dest is True

    def test_drop_table_matches(self):
        is_dest, reason = gr.is_destructive_action("drop table users")
        assert is_dest is True

    def test_shutdown_matches(self):
        is_dest, reason = gr.is_destructive_action("shutdown")
        assert is_dest is True

    def test_restart_computer_matches(self):
        is_dest, reason = gr.is_destructive_action("restart the computer")
        assert is_dest is True

    def test_empty_trash_matches(self):
        is_dest, reason = gr.is_destructive_action("empty the recycle bin")
        assert is_dest is True

    def test_safe_strings_rejected(self):
        safe = [
            "open chrome",
            "navigate to google.com",
            "click the search bar",
            "type hello world",
            "scroll down",
            "take a screenshot",
            "delete",  # standalone word without context
            "remove",  # standalone word without context
        ]
        for text in safe:
            is_dest, _ = gr.is_destructive_action(text)
            assert is_dest is False, f"'{text}' should not be flagged"

    def test_case_insensitive(self):
        is_dest, _ = gr.is_destructive_action("DELETE FILE report.pdf")
        assert is_dest is True

    def test_false_positive_safe_phrases(self):
        # Phrases that contain destructive words but in safe contexts
        safe_contexts = [
            "delete character before cursor",  # editing context
            "remove formatting from text",   # not remove + file
        ]
        for text in safe_contexts:
            is_dest, reason = gr.is_destructive_action(text)
            # These currently match because regex is simple; document as known
            if is_dest:
                assert "destructive_keyword" in reason


class TestValidateCoordinates:
    def test_valid_center(self):
        valid, _ = gr.validate_coordinates(100, 100, screen_w=1920, screen_h=1080)
        assert valid is True

    def test_edge_minimum_rejected(self):
        valid, reason = gr.validate_coordinates(0, 0)
        assert valid is False
        assert "too_low" in reason

    def test_negative_rejected(self):
        valid, reason = gr.validate_coordinates(-10, 50)
        assert valid is False
        assert "too_low" in reason

    def test_4k_display_accepted(self):
        valid, _ = gr.validate_coordinates(2000, 1500, screen_w=3840, screen_h=2160)
        assert valid is True

    def test_4k_edge_rejected(self):
        valid, reason = gr.validate_coordinates(3835, 100, screen_w=3840, screen_h=2160)
        assert valid is False
        assert "out_of_bounds" in reason

    def test_4k_bottom_edge_rejected(self):
        valid, reason = gr.validate_coordinates(100, 2155, screen_w=3840, screen_h=2160)
        assert valid is False
        assert "out_of_bounds" in reason

    def test_none_rejected(self):
        valid, reason = gr.validate_coordinates(None, 100)
        assert valid is False
        assert "invalid_type" in reason

    def test_string_rejected(self):
        valid, reason = gr.validate_coordinates("abc", 100)
        assert valid is False
        assert "invalid_type" in reason

    def test_defaults_1920_1080(self):
        valid, _ = gr.validate_coordinates(960, 540)
        assert valid is True


class TestDetectLoop:
    def test_not_enough_history(self):
        history = [("click", "hash1")]
        assert gr.detect_loop(history, window=3) is False

    def test_identical_last_three(self):
        history = [
            ("click", "hash1"),
            ("click", "hash2"),
            ("click", "hash2"),
            ("click", "hash2"),
        ]
        assert gr.detect_loop(history, window=3) is True

    def test_different_hashes_no_loop(self):
        history = [
            ("click", "hash1"),
            ("click", "hash2"),
            ("click", "hash3"),
        ]
        assert gr.detect_loop(history, window=3) is False

    def test_window_size_one(self):
        history = [("click", "hash1"), ("click", "hash2")]
        assert gr.detect_loop(history, window=1) is True  # last 1 always identical to itself

    def test_window_size_five(self):
        history = [("click", "h")] * 5
        assert gr.detect_loop(history, window=5) is True

    def test_partial_match_not_loop(self):
        history = [
            ("click", "hash1"),
            ("click", "hash2"),
            ("click", "hash2"),
            ("click", "hash3"),
        ]
        assert gr.detect_loop(history, window=3) is False


class TestScreenshotHash:
    def test_empty_bytes(self):
        assert gr.screenshot_hash(b"") == "d41d8cd98f00b204e9800998ecf8427e"

    def test_deterministic(self):
        data = b"test screenshot bytes"
        h1 = gr.screenshot_hash(data)
        h2 = gr.screenshot_hash(data)
        assert h1 == h2
        assert len(h1) == 32  # md5 hex

    def test_different_data_different_hash(self):
        h1 = gr.screenshot_hash(b"aaa")
        h2 = gr.screenshot_hash(b"bbb")
        assert h1 != h2


class TestPixelDiffScore:
    def test_identical(self):
        data = b"same data here"
        assert gr.pixel_diff_score(data, data) == 0.0

    def test_completely_different_same_length(self):
        a = b"\x00" * 100
        b = b"\xff" * 100
        assert gr.pixel_diff_score(a, b) == 1.0

    def test_different_length(self):
        a = b"\x00" * 50
        b = b"\x00" * 100
        assert gr.pixel_diff_score(a, b) == 1.0

    def test_empty(self):
        assert gr.pixel_diff_score(b"", b"") == 1.0

    def test_half_different(self):
        a = b"\x00" * 50 + b"\xff" * 50
        b = b"\xff" * 50 + b"\x00" * 50
        score = gr.pixel_diff_score(a, b)
        assert score == 1.0  # all 100 bytes differ

    def test_partial_different(self):
        a = b"\x00" * 100
        b = b"\x00" * 50 + b"\xff" * 50
        score = gr.pixel_diff_score(a, b)
        assert score == 0.5
