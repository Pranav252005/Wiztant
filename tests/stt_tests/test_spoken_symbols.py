"""Tests for spoken-symbol and entity dictation corrections.

Covers:
  - dot-com / dot-py re-glue (no space after dot)
  - standalone slash → /
  - ut → @  (phonetic "at")
  - at the rate → @
  - wind surf → Windsurf
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import pytest

from core.voice import clean_transcript
from core.dictation_smart import smart_dictate


class TestCleanTranscriptSpokenSymbols:
    """Layer 1 spoken-pattern corrections in voice.py."""

    @pytest.mark.parametrize("spoken,expected", [
        ("test dot com", "Test.com"),
        ("test dot py", "Test.py"),
        ("test dot js", "Test.js"),
        ("test dot json", "Test.JSON"),
        ("test dot env", "Test.env"),
        ("test dot git", "Test.Git"),
        ("my site dot io", "My site.io"),
    ])
    def test_dot_extensions_not_spaced(self, spoken: str, expected: str):
        """dot <word> must produce .<word> without a space."""
        result = clean_transcript(spoken)
        assert result == expected, f"got {result!r}"

    @pytest.mark.parametrize("spoken,expected", [
        ("use slash", "Use/"),
        ("press slash now", "Press/ now"),
        ("forward slash", "/"),
    ])
    def test_slash_standalone(self, spoken: str, expected: str):
        """Standalone 'slash' must become '/' character."""
        result = clean_transcript(spoken)
        assert result == expected, f"got {result!r}"

    @pytest.mark.parametrize("spoken,expected", [
        ("email ut gmail", "Email @ gmail"),
        ("type ut sign", "Type @ sign"),
        ("at the rate gmail", "@ gmail"),
    ])
    def test_at_symbol_variants(self, spoken: str, expected: str):
        """'ut' and 'at the rate' must become '@'."""
        result = clean_transcript(spoken)
        assert result == expected, f"got {result!r}"

    def test_wind_surf_collapsed(self):
        """Two-word 'wind surf' must collapse to 'Windsurf'."""
        result = clean_transcript("open wind surf now")
        assert "Windsurf" in result
        assert "wind surf" not in result.lower()

    def test_combined_symbols_and_extensions(self):
        """Multiple patterns in one sentence."""
        result = clean_transcript("use slash and dot py files")
        assert "/" in result
        assert ".py" in result
        assert ". py" not in result


class TestSmartDictateSpokenSymbols:
    """End-to-end corrections through the smart_dictate pipeline.

    smart_dictate() runs AFTER clean_transcript(), so its inputs are
    already partially converted.  These tests verify the re-glue and
    defensive symbol layers.
    """

    @pytest.mark.parametrize("pre_cleaned,expected", [
        ("test. com", "test.com"),
        ("test. py", "test.py"),
        ("config. env", "config.env"),
    ])
    def test_reglue_spaced_extensions(self, pre_cleaned: str, expected: str):
        """Re-glue must fix . com → .com etc."""
        result = smart_dictate(pre_cleaned)
        assert result["text"] == expected, f"got {result['text']!r}"

    def test_reglue_at_and_slash(self):
        """Re-glue @ and / with their following tokens."""
        result = smart_dictate("contact @ gmail. com")
        assert result["text"] == "contact @gmail.com"

    def test_defensive_symbols(self):
        """Symbols that reach dictation_smart layer are still converted."""
        result = smart_dictate("use slash ut sign")
        text = result["text"]
        assert "/" in text
        assert "@" in text
        assert "slash" not in text.lower()
        assert "ut" not in text.lower()

    def test_wind_surf_entity(self):
        """Entity fix for 'wind surf' through smart_dictate."""
        result = smart_dictate("open wind surf")
        assert "Windsurf" in result["text"]


class TestFullPipeline:
    """Simulate the real hotkeys.py pipeline: clean_transcript → smart_dictate."""

    def test_email_at_the_rate_dot_com(self):
        spoken = "my email is test at the rate gmail dot com"
        cleaned = clean_transcript(spoken)
        final = smart_dictate(cleaned)["text"]
        # clean_transcript turns "at the rate" into "@" with surrounding spaces;
        # re-glue fixes the space after @, so we get "test @gmail.com".
        assert "test @gmail.com" in final, f"got {final!r}"

    def test_use_slash_path(self):
        spoken = "use slash home slash pranav"
        cleaned = clean_transcript(spoken)
        final = smart_dictate(cleaned)["text"]
        # _smart_punctuation removes space before /, so "home /" becomes "home/".
        assert "/" in final
        assert "home/" in final or "home /" in final, f"got {final!r}"

    def test_dot_py_no_space(self):
        spoken = "open dot py file"
        cleaned = clean_transcript(spoken)
        final = smart_dictate(cleaned)["text"]
        assert ".py" in final
        assert ". py" not in final
