"""Tests for core/agent_engine.py utilities — parse_json, call_api mocking, to_base64."""

import base64
import json
import sys
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PIL import Image

from core import agent_engine as engine


class TestParseJson:
    def test_empty_string(self):
        assert engine.parse_json("") is None

    def test_plain_json(self):
        result = engine.parse_json('{"action": "click", "x": 10}')
        assert result == {"action": "click", "x": 10}

    def test_json_with_code_fence(self):
        result = engine.parse_json('```json\n{"action": "click"}\n```')
        assert result == {"action": "click"}

    def test_json_with_thinking_tags(self):
        text = '<thinking>let me think...</thinking>\n{"action": "click"}'
        result = engine.parse_json(text)
        assert result == {"action": "click"}

    def test_nested_code_fence(self):
        text = 'Some explanation\n```json\n{"action": "type", "text": "hello"}\n```\nMore text'
        result = engine.parse_json(text)
        assert result == {"action": "type", "text": "hello"}

    def test_invalid_then_literal_eval_fallback(self):
        # Python dict literal (single quotes) — json.loads fails, ast.literal_eval succeeds
        text = "{'action': 'click', 'x': 10}"
        result = engine.parse_json(text)
        assert result == {"action": "click", "x": 10}

    def test_completely_invalid(self):
        assert engine.parse_json("not json at all") is None

    def test_trailing_whitespace_after_fence(self):
        text = '```json\n{"action": "click"}\n```   \n'
        result = engine.parse_json(text)
        assert result == {"action": "click"}

    def test_multiple_braces(self):
        text = 'prefix {"inner": 1} suffix {"action": "click"}'
        result = engine.parse_json(text)
        # Should grab first valid JSON-like brace pair
        assert "inner" in result or "action" in result

    def test_json_list(self):
        result = engine.parse_json('[1, 2, 3]')
        assert result == [1, 2, 3]


class TestCallApi:
    def test_successful_mock(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "response text"
        mock_client.chat.completions.create.return_value = mock_response

        with patch.object(engine, "_client", mock_client):
            result = engine.call_api("gpt-4o", [{"role": "user", "content": "hi"}], 0.7, 100)
        assert result == "response text"

    def test_api_failure_returns_empty(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("API down")

        with patch.object(engine, "_client", mock_client):
            result = engine.call_api("gpt-4o", [{"role": "user", "content": "hi"}], 0.7, 100)
        assert result == ""

    def test_thinking_false_adds_extra_body(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "ok"
        mock_client.chat.completions.create.return_value = mock_response

        with patch.object(engine, "_client", mock_client):
            engine.call_api("gpt-4o", [{"role": "user", "content": "hi"}], 0.7, 100, thinking=False)

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "extra_body" in call_kwargs
        assert call_kwargs["extra_body"] == {"include_reasoning": False}

    def test_thinking_true_no_extra_body(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "ok"
        mock_client.chat.completions.create.return_value = mock_response

        with patch.object(engine, "_client", mock_client):
            engine.call_api("gpt-4o", [{"role": "user", "content": "hi"}], 0.7, 100, thinking=True)

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "extra_body" not in call_kwargs


class TestToBase64:
    def test_small_image_no_resize(self):
        img = Image.new("RGB", (100, 100), color="red")
        b64 = engine.to_base64(img, max_side=960)
        decoded = base64.b64decode(b64)
        restored = Image.open(BytesIO(decoded))
        assert restored.size == (100, 100)

    def test_large_image_resized(self):
        img = Image.new("RGB", (2000, 1000), color="blue")
        b64 = engine.to_base64(img, max_side=960)
        decoded = base64.b64decode(b64)
        restored = Image.open(BytesIO(decoded))
        # max side should be scaled down to 960
        assert restored.size[0] == 960
        assert restored.size[1] == 480  # proportional

    def test_jpeg_format(self):
        img = Image.new("RGB", (100, 100))
        b64 = engine.to_base64(img)
        decoded = base64.b64decode(b64)
        # JPEG magic bytes
        assert decoded[:2] == b"\xff\xd8"


class TestCanonicalizeUrl:
    def test_empty(self):
        assert engine.canonicalize_url("") == ""

    def test_adds_https(self):
        assert engine.canonicalize_url("google.com") == "https://google.com"

    def test_twitter_to_x(self):
        assert engine.canonicalize_url("twitter.com") == "https://x.com"

    def test_www_stripped(self):
        assert engine.canonicalize_url("https://www.example.com") == "https://example.com"


class TestRefineTaskText:
    def test_removes_fillers(self):
        refined = engine.refine_task_text("please kindly open twitter for me")
        assert "please" not in refined.lower()
        assert "kindly" not in refined.lower()
        assert "twitter" not in refined.lower()  # canonicalized to x.com
        assert "x.com" in refined.lower()

    def test_click_on_normalized(self):
        refined = engine.refine_task_text("click on the button")
        assert "click on" not in refined.lower()
        assert "click" in refined.lower()

    def test_sign_in_normalized(self):
        refined = engine.refine_task_text("log in to the site")
        assert "log in" not in refined.lower()
        assert "sign in" in refined.lower()

    def test_whitespace_collapsed(self):
        refined = engine.refine_task_text("  open   chrome   ")
        assert "  " not in refined
        assert refined == "open chrome"


class TestIsResearchTask:
    def test_search_is_research(self):
        assert engine.is_research_task("search for python docs") is True

    def test_open_app_is_not_research(self):
        assert engine.is_research_task("open chrome") is False

    def test_calculate_is_research(self):
        assert engine.is_research_task("calculate 2+2") is True


class TestFindKeyboardShortcut:
    def test_known_shortcut(self):
        result = engine.find_keyboard_shortcut("new tab")
        assert result == ["ctrl", "t"]

    def test_unknown_shortcut(self):
        assert engine.find_keyboard_shortcut("do a backflip") is None

    def test_case_insensitive(self):
        result = engine.find_keyboard_shortcut("NEW TAB")
        assert result == ["ctrl", "t"]


class TestEntryCategory:
    def test_settings_is_a(self):
        assert engine.entry_category("settings") == "A"

    def test_explorer_is_b(self):
        assert engine.entry_category("explorer") == "B"

    def test_chrome_is_d(self):
        assert engine.entry_category("chrome") == "D"

    def test_unknown_is_c(self):
        assert engine.entry_category("some_unknown_app") == "C"


class TestQuickPreflight:
    def test_research_task_returns_none(self):
        result = engine.quick_preflight("what is the weather today")
        assert result is None

    def test_browser_task_returns_dict(self):
        result = engine.quick_preflight("open chrome and go to google.com")
        assert isinstance(result, dict)
        assert result["app_to_open"] == "chrome"
        assert result["needs_research"] is False

    def test_click_target_extracted(self):
        result = engine.quick_preflight("click the submit button in chrome")
        assert result is not None
        assert "submit button" in result.get("strategy", "")
