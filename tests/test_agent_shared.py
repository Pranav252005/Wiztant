"""
tests/test_agent_shared.py — Smoke tests for shared agent core & platform backends.
These tests verify imports, constants, and pure functions without requiring API keys.
"""
import sys
from unittest.mock import patch


def test_import_agent_engine():
    from core.agent_engine import (
        BROWSER_APPS,
        EXEC_MAX_TOKENS,
        EXECUTOR_MODEL,
        GROUND_IMG_MAX,
        KNOWN_APPS,
        MAX_LOOP_STEPS,
        MAX_RESULT_SCROLLS,
        OMNI_MODEL,
        PLAN_MAX_TOKENS,
        PLAN_SYSTEM,
        SITE_ALIASES,
        SITE_URLS,
        STEP_PAUSE,
        TEMP_EXEC,
        TEMP_PLAN,
        TEMP_TARS,
        TEMP_THINK,
        TARS_MAX_TOKENS,
        THINK_MAX_TOKENS,
        THINK_SYSTEM,
        call_api,
        canonicalize_url,
        canonical_site_label,
        entry_category,
        extract_click_target,
        extract_requested_app,
        extract_requested_url,
        find_keyboard_shortcut,
        is_research_task,
        parse_json,
        quick_preflight,
        refine_element_target,
        refine_task_text,
        to_base64,
    )

    assert "chrome" in KNOWN_APPS
    assert "x.com" in SITE_URLS["twitter"]
    assert MAX_LOOP_STEPS > 0
    assert GROUND_IMG_MAX >= 640


def test_import_platform_backends():
    from core.platform_backends import (
        click,
        cursor_position,
        ensure_app_open,
        get_foreground_app,
        hotkey,
        launch_app,
        launch_browser,
        list_monitors,
        modifier_key,
        move,
        ocr_image,
        platform_name,
        press_key,
        raise_window,
        screenshot,
        scroll,
        screen_size,
        translate_coordinates,
        type_text,
        validate_screen_coordinates,
    )

    assert platform_name() in ("windows", "linux")
    assert modifier_key() in ("win", "super")
    assert list_monitors() is not None


def test_import_vlm_linux():
    from platforms.linux._vlm_impl import (
        capture_window_screenshot,
        run_agent_loop,
        run_agent_task,
        run_agent_task_async,
    )
    assert callable(run_agent_loop)
    assert callable(run_agent_task)
    assert callable(run_agent_task_async)


def test_import_linux_wrapper():
    from platforms.linux.vlm import LinuxVLM
    vlm = LinuxVLM()
    assert callable(vlm.capture)
    assert callable(vlm.run_agent_loop)


def test_text_utilities():
    from core.agent_engine import (
        canonicalize_url,
        canonical_site_label,
        refine_element_target,
        refine_task_text,
        is_research_task,
    )

    assert canonicalize_url("twitter.com") == "https://x.com"
    assert canonicalize_url("youtube.com") == "https://youtube.com"
    assert canonical_site_label("https://www.google.com/search") == "google.com"
    assert "sign in button" in refine_element_target("sign in")
    assert "x.com" in refine_task_text("go to twitter.com")
    assert is_research_task("what is the weather") is True
    assert is_research_task("open chrome") is False


def test_quick_preflight_browser():
    from core.agent_engine import quick_preflight

    result = quick_preflight("open chrome and go to youtube.com")
    assert result is not None
    assert result["app_to_open"] == "chrome"
    assert result["needs_research"] is False


def test_quick_preflight_non_browser():
    from core.agent_engine import quick_preflight

    result = quick_preflight("what is the capital of France")
    assert result is None  # research task


def test_parse_json():
    from core.agent_engine import parse_json

    assert parse_json('{"action": "click"}') == {"action": "click"}
    assert parse_json('```json\n{"action": "click"}\n```') == {"action": "click"}
    assert parse_json("invalid json") is None


def test_translate_coordinates():
    from core.platform_backends import translate_coordinates

    with patch("core.platform_backends.screen_size", return_value=(1920, 1080)):
        result = translate_coordinates(500, 500)
        assert result == (960, 540)

    assert translate_coordinates("abc", 500) is None
    assert translate_coordinates(1500, 500) is None


def test_keyboard_shortcuts():
    from core.agent_engine import find_keyboard_shortcut

    assert find_keyboard_shortcut("new tab") == ["ctrl", "t"]
    assert find_keyboard_shortcut("address bar") == ["ctrl", "l"]
    assert find_keyboard_shortcut("nonexistent") is None


def test_entry_category():
    from core.agent_engine import entry_category

    assert entry_category("chrome") == "D"
    assert entry_category("vscode") == "E"
    assert entry_category("slack") == "F"
    assert entry_category("terminal") == "G"
    assert entry_category("settings") == "A"


def test_vlm_linux_legacy_helpers_exist():
    from platforms.linux._vlm_impl import (
        _ensure_app_open,
        _get_foreground_app,
        _perform_click,
        _perform_click_from_model,
        _press_key,
        _scroll_at,
        _type_text,
        _take_screenshot,
    )
    assert callable(_ensure_app_open)
    assert callable(_get_foreground_app)
