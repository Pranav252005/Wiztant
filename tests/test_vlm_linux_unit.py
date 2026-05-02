"""Unit tests for platforms/linux/_vlm_impl.py — mocked execution pipeline."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PIL import Image


@pytest.fixture(autouse=True)
def _no_external_calls(monkeypatch):
    """Prevent real API calls and platform actions during tests."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("AGENT_OMNI_MODEL", "test-model")
    monkeypatch.setenv("AGENT_EXECUTOR_MODEL", "test-executor")


def _mock_image(size=(100, 100)):
    return Image.new("RGB", size, color="red")


class TestPreflight:
    def test_research_task_returns_none(self):
        from platforms.linux._vlm_impl import _preflight
        with patch("platforms.linux._vlm_impl.quick_preflight", return_value=None):
            with patch("platforms.linux._vlm_impl.call_api", return_value='{"needs_research": true}'):
                with patch("platforms.linux._vlm_impl.parse_json", return_value={"needs_research": True}):
                    result = _preflight("what is the weather")
                    assert isinstance(result, dict)

    def test_quick_preflight_fast_path(self):
        from platforms.linux._vlm_impl import _preflight
        fake = {"clean_task": "open chrome", "app_to_open": "chrome", "strategy": "browser"}
        with patch("platforms.linux._vlm_impl.quick_preflight", return_value=fake):
            result = _preflight("open chrome and go to google")
            assert result["app_to_open"] == "chrome"


class TestHeuristicPlan:
    def test_no_app_url_click_returns_none(self):
        from platforms.linux._vlm_impl import _heuristic_plan
        result = _heuristic_plan("do something vague", {"app_to_open": "", "clean_task": "do something vague"})
        assert result is None

    def test_app_name_generates_steps(self):
        from platforms.linux._vlm_impl import _heuristic_plan
        preflight = {"app_to_open": "chrome", "clean_task": "open chrome"}
        result = _heuristic_plan("open chrome", preflight)
        assert result is not None
        assert result["initial_action"]["type"] == "open_app"
        assert result["initial_action"]["app"] == "chrome"

    def test_url_generates_browser_plan(self):
        from platforms.linux._vlm_impl import _heuristic_plan
        preflight = {"app_to_open": "", "clean_task": "navigate to google.com"}
        result = _heuristic_plan("go to google.com", preflight)
        assert result is not None
        assert any("Navigate" in s for s in result["steps"])


class TestExecute:
    def test_open_app_action(self):
        from platforms.linux._vlm_impl import _execute
        with patch("platforms.linux._vlm_impl.launch_browser", return_value="launched chrome"):
            result = _execute({"type": "open_app", "app": "chrome"})
            assert "launched" in result.lower()

    def test_hotkey_action(self):
        from platforms.linux._vlm_impl import _execute
        with patch("platforms.linux._vlm_impl.hotkey", return_value=(True, "hotkey ctrl+t")):
            result = _execute({"type": "hotkey", "keys": ["ctrl", "t"]})
            assert "hotkey" in result.lower()

    def test_hotkey_string_keys(self):
        from platforms.linux._vlm_impl import _execute
        with patch("platforms.linux._vlm_impl.hotkey", return_value=(True, "hotkey ctrl+t")):
            result = _execute({"type": "hotkey", "keys": "ctrl+t"})
            assert "hotkey" in result.lower()

    def test_type_action(self):
        from platforms.linux._vlm_impl import _execute
        with patch("platforms.linux._vlm_impl.type_text", return_value=(True, "typed 'hello'")):
            result = _execute({"type": "type", "text": "hello"})
            assert "typed" in result.lower()

    def test_press_action(self):
        from platforms.linux._vlm_impl import _execute
        with patch("platforms.linux._vlm_impl.press_key", return_value=(True, "pressed enter")):
            result = _execute({"type": "press", "key": "enter"})
            assert "pressed" in result.lower()

    def test_press_list_keys(self):
        from platforms.linux._vlm_impl import _execute
        with patch("platforms.linux._vlm_impl.hotkey", return_value=(True, "hotkey")):
            result = _execute({"type": "press", "key": ["ctrl", "c"]})
            assert "hotkey" in result.lower()

    def test_click_action_with_coordinates(self):
        from platforms.linux._vlm_impl import _execute
        with patch("platforms.linux._vlm_impl.translate_coordinates", return_value=(100, 200)):
            with patch("platforms.linux._vlm_impl.click", return_value=(True, "clicked")):
                result = _execute({"type": "click", "coordinates": [500, 500]})
                assert "clicked" in result.lower()

    def test_click_action_invalid_coords(self):
        from platforms.linux._vlm_impl import _execute
        with patch("platforms.linux._vlm_impl.translate_coordinates", return_value=None):
            result = _execute({"type": "click", "coordinates": [500, 500]})
            assert "invalid" in result.lower()

    def test_click_action_xy_keys(self):
        from platforms.linux._vlm_impl import _execute
        with patch("platforms.linux._vlm_impl.translate_coordinates", return_value=(100, 200)):
            with patch("platforms.linux._vlm_impl.click", return_value=(True, "clicked")):
                result = _execute({"type": "click", "x": 500, "y": 500})
                assert "clicked" in result.lower()

    def test_scroll_action(self):
        from platforms.linux._vlm_impl import _execute
        with patch("platforms.linux._vlm_impl.translate_coordinates", return_value=(100, 200)):
            with patch("platforms.linux._vlm_impl.scroll", return_value=(True, "scrolled")):
                result = _execute({"type": "scroll", "coordinates": [500, 500], "amount": 3})
                assert "scrolled" in result.lower()

    def test_wait_action(self):
        from platforms.linux._vlm_impl import _execute
        import time
        start = time.time()
        result = _execute({"type": "wait", "seconds": 0.05})
        elapsed = time.time() - start
        assert elapsed >= 0.04
        assert "waited" in result.lower()

    def test_navigate_action(self):
        from platforms.linux._vlm_impl import _execute
        with patch("platforms.linux._vlm_impl.ensure_app_open", return_value="ok"):
            with patch("platforms.linux._vlm_impl.hotkey", return_value=(True, "ok")):
                with patch("platforms.linux._vlm_impl.type_text", return_value=(True, "ok")):
                    with patch("platforms.linux._vlm_impl.press_key", return_value=(True, "ok")):
                        result = _execute({"type": "navigate", "url": "https://example.com", "app": "chrome"})
                        assert "navigated" in result.lower()

    def test_ask_uitars_action(self):
        from platforms.linux._vlm_impl import _execute
        with patch("platforms.linux._vlm_impl.find_keyboard_shortcut", return_value=None):
            with patch("platforms.linux._vlm_impl.screenshot", return_value=_mock_image()):
                with patch("platforms.linux._vlm_impl._ask_uitars_executor", return_value={"action": "click", "x": 500, "y": 500}):
                    with patch("platforms.linux._vlm_impl.translate_coordinates", return_value=(100, 200)):
                        with patch("platforms.linux._vlm_impl.click", return_value=(True, "clicked")):
                            result = _execute({"type": "ask_uitars", "instruction": "click the button"})
                            assert "clicked" in result.lower()

    def test_ask_uitars_not_found(self):
        from platforms.linux._vlm_impl import _execute
        with patch("platforms.linux._vlm_impl.find_keyboard_shortcut", return_value=None):
            with patch("platforms.linux._vlm_impl.screenshot", return_value=_mock_image()):
                with patch("platforms.linux._vlm_impl._ask_uitars_executor", return_value=None):
                    result = _execute({"type": "ask_uitars", "instruction": "click the button"})
                    assert "could not find" in result.lower()

    def test_screenshot_action(self):
        from platforms.linux._vlm_impl import _execute
        with patch("platforms.linux._vlm_impl.screenshot", return_value=_mock_image()):
            with patch("platforms.linux._vlm_impl.ocr_image", return_value="hello world"):
                result = _execute({"type": "screenshot"})
                assert "Screenshot captured" in result
                assert "hello world" in result

    def test_done_action(self):
        from platforms.linux._vlm_impl import _execute
        result = _execute({"type": "done", "result": "completed successfully"})
        assert result == "completed successfully"

    def test_done_message_key(self):
        from platforms.linux._vlm_impl import _execute
        result = _execute({"type": "done", "message": "all done"})
        assert result == "all done"

    def test_failed_action(self):
        from platforms.linux._vlm_impl import _execute
        result = _execute({"type": "failed", "message": "could not find element"})
        assert "could not find element" in result

    def test_unknown_action(self):
        from platforms.linux._vlm_impl import _execute
        result = _execute({"type": "fly_to_the_moon"})
        assert "unknown action" in result.lower()

    def test_open_app_with_browser_url(self):
        from platforms.linux._vlm_impl import _execute
        with patch("platforms.linux._vlm_impl.launch_browser", return_value="launched arc"):
            result = _execute({"type": "open_app", "app": "arc", "url": "https://example.com"})
            assert "launched" in result.lower()

    def test_find_video_result_success(self):
        from platforms.linux._vlm_impl import _execute
        with patch("platforms.linux._vlm_impl.screenshot", return_value=_mock_image()):
            with patch("platforms.linux._vlm_impl._ask_uitars_executor", return_value={"action": "click", "x": 500, "y": 500}):
                with patch("platforms.linux._vlm_impl.translate_coordinates", return_value=(100, 200)):
                    with patch("platforms.linux._vlm_impl.click", return_value=(True, "clicked")):
                        result = _execute({"type": "find_video_result", "query": "python tutorial"})
                        assert "clicked" in result.lower()

    def test_find_video_result_gives_up(self):
        from platforms.linux._vlm_impl import _execute
        with patch("platforms.linux._vlm_impl.screenshot", return_value=_mock_image()):
            with patch("platforms.linux._vlm_impl._ask_uitars_executor", return_value=None):
                with patch("platforms.linux._vlm_impl.scroll", return_value=(True, "scrolled")):
                    result = _execute({"type": "find_video_result", "query": "python tutorial", "max_scrolls": 1})
                    assert "failed" in result.lower()

    def test_progress_callback_fired(self):
        from platforms.linux._vlm_impl import _execute
        cb = MagicMock()
        with patch("platforms.linux._vlm_impl.hotkey", return_value=(True, "ok")):
            _execute({"type": "hotkey", "keys": ["ctrl", "t"]}, progress_cb=cb)
        cb.assert_called_once()


class TestInstructionVariants:
    def test_basic_variants(self):
        from platforms.linux._vlm_impl import _instruction_variants
        result = _instruction_variants("click the submit button")
        assert "click the submit button" in result
        assert "click submit button" in result

    def test_sign_in_expansion(self):
        from platforms.linux._vlm_impl import _instruction_variants
        result = _instruction_variants("click sign in")
        assert any("sign in button" in r.lower() for r in result)

    def test_empty_returns_empty(self):
        from platforms.linux._vlm_impl import _instruction_variants
        assert _instruction_variants("") == []


class TestSanitizePlan:
    def test_click_with_coords_converted_to_ask_uitars(self):
        from platforms.linux._vlm_impl import _sanitize_plan
        plan = {"steps": [{"action": {"type": "click", "x": 10, "y": 20}}]}
        result = _sanitize_plan(plan)
        step = result["steps"][0]
        assert step["action"]["type"] == "ask_uitars"

    def test_plain_string_step_preserved(self):
        from platforms.linux._vlm_impl import _sanitize_plan
        plan = {"steps": ["open chrome"]}
        result = _sanitize_plan(plan)
        assert result["steps"][0] == "open chrome"

    def test_non_click_dict_preserved(self):
        from platforms.linux._vlm_impl import _sanitize_plan
        plan = {"steps": [{"action": {"type": "hotkey", "keys": ["ctrl", "t"]}}]}
        result = _sanitize_plan(plan)
        assert result["steps"][0]["action"]["type"] == "hotkey"
