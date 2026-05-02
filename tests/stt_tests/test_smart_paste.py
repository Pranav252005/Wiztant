"""Unit tests for smart paste engine."""

import pytest
from core.smart_paste import SmartPasteEngine


class TestSmartPasteEngine:
    @pytest.fixture
    def engine(self):
        return SmartPasteEngine()

    def test_format_task_basic(self, engine):
        """Basic task formatting."""
        result = engine.format_for_task("call john about the deadline")
        assert result == "Call john about the deadline"

    def test_format_task_removes_fillers(self, engine):
        """Remove filler words from end."""
        result = engine.format_for_task("create a task for um the project um")
        assert "um" not in result
        assert result.startswith("Create")

    def test_format_task_whitespace_trim(self, engine):
        """Trim whitespace."""
        result = engine.format_for_task("   test   ")
        assert result == "Test"

    def test_format_task_removes_trailing_period(self, engine):
        """Remove trailing periods."""
        result = engine.format_for_task("create a task.")
        assert not result.endswith(".")

    def test_format_task_empty_input(self, engine):
        """Handle empty input."""
        result = engine.format_for_task("")
        assert result == ""
        result = engine.format_for_task("   ")
        assert result == ""

    def test_format_description_multisentence(self, engine):
        """Format multi-sentence description."""
        text = "this is first. this is second. this is third"
        result = engine.format_for_description(text)
        assert result.count(".") >= 2
        assert "This" in result

    def test_format_description_empty(self, engine):
        """Empty description."""
        result = engine.format_for_description("")
        assert result == ""

    def test_clear_clipboard(self, engine):
        """Clear clipboard operation."""
        result = engine.clear_clipboard()
        assert isinstance(result, bool)

    def test_copy_to_clipboard(self, engine):
        """Copy to clipboard."""
        result = engine.copy_to_clipboard("test text")
        assert result is True

    def test_paste_stats_initial(self, engine):
        """Paste statistics start at zero."""
        assert engine.paste_stats["total_pastes"] == 0
        assert engine.paste_stats["successful"] == 0

    def test_get_last_paste_none(self, engine):
        """Retrieve last paste before any paste."""
        assert engine.get_last_paste() is None

    def test_reset_paste_stats(self, engine):
        """Reset stats clears counters."""
        engine.paste_stats["successful"] = 5
        engine.reset_paste_stats()
        assert engine.paste_stats["successful"] == 0

    def test_format_task_caps_first_letter(self, engine):
        """Capitalize first letter."""
        result = engine.format_for_task("lower case start")
        assert result[0].isupper()

    def test_format_task_no_change_needed(self, engine):
        """Already formatted text passes through."""
        result = engine.format_for_task("Call John about the deadline")
        assert result == "Call John about the deadline"
