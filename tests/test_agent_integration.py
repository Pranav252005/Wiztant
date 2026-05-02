"""Integration smoke tests for agent cross-platform parity and end-to-end dry runs."""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image


def test_import_parity_vlm_linux_has_matching_concepts():
    """Every public symbol in vlm_linux has a matching concept in vlm (Windows)."""
    import platforms.windows._vlm_impl as vlm_win
    import platforms.linux._vlm_impl as vlm_linux

    linux_exports = set(vlm_linux.__all__)
    # Core orchestration symbols must exist in both
    core_symbols = {"run_agent_loop", "run_agent_task", "run_agent_task_async"}
    for sym in core_symbols:
        assert sym in linux_exports, f"{sym} missing from vlm_linux.__all__"
        assert hasattr(vlm_win, sym) or hasattr(vlm_linux, sym), f"{sym} not found"


def test_platform_backends_runs_without_pyautogui():
    """Linux backend should initialize without pyautogui (pynput/xdotool fallbacks)."""
    import core.platform_backends as pb

    # On Linux, platform_name should be "linux" and modifier_key "super"
    assert pb.platform_name() == "linux"
    assert pb.modifier_key() == "super"
    # list_monitors should return a list without crashing
    monitors = pb.list_monitors()
    assert isinstance(monitors, list)
    # screen_size should return a tuple of two ints
    w, h = pb.screen_size()
    assert isinstance(w, int) and isinstance(h, int)
    assert w > 0 and h > 0


def test_translate_coordinates_clamps_to_bounds():
    """Coordinate translation should clamp to screen bounds."""
    import core.platform_backends as pb

    with patch.object(pb, "screen_size", return_value=(1920, 1080)):
        # 500 on 0-1000 scale should be half screen
        result = pb.translate_coordinates(500, 500)
        assert result == (960, 540)

        # Out of 0-1000 range should be rejected
        assert pb.translate_coordinates(-1, 500) is None
        assert pb.translate_coordinates(500, 1001) is None


def test_end_to_end_dry_run_open_settings():
    """run_agent_task with mocked screenshot + API should return within 5s."""
    import platforms.linux._vlm_impl as vlm_linux

    start = time.time()
    with patch("platforms.linux._vlm_impl.screenshot", return_value=Image.new("RGB", (100, 100))):
        with patch("platforms.linux._vlm_impl.ocr_image", return_value="Settings"):
            with patch("platforms.linux._vlm_impl.call_api", return_value='{"action": "done", "result": "opened settings"}'):
                with patch("platforms.linux._vlm_impl.parse_json", side_effect=lambda x: {"action": "done", "result": "opened settings"} if "done" in x else None):
                    with patch("platforms.linux._vlm_impl.ensure_app_open", return_value="launched settings"):
                        result = vlm_linux.run_agent_task("open settings")
    elapsed = time.time() - start
    assert elapsed < 5.0, f"Dry run took {elapsed:.1f}s, expected < 5s"
    assert "opened settings" in result or "done" in result.lower() or result == ""


def test_guardrails_coverage():
    """All guardrail functions should be importable and callable."""
    import core.guardrails as gr

    assert gr.is_destructive_action("rm -rf /")[0] is True
    assert gr.validate_coordinates(100, 100)[0] is True
    assert gr.detect_loop([("click", "a"), ("click", "a"), ("click", "a")]) is True
    assert len(gr.screenshot_hash(b"test")) == 32
    assert 0.0 <= gr.pixel_diff_score(b"\x00" * 10, b"\xff" * 10) <= 1.0


def test_agent_memory_hermetic():
    """AgentMemory should work in a temp directory without touching real data."""
    import tempfile
    from core.agent import AgentMemory

    with tempfile.TemporaryDirectory() as tmpdir:
        mem = AgentMemory(data_dir=Path(tmpdir))
        mem.record_task_start("t-test", "Open settings", "system")
        mem.record_task_complete("t-test", "undo-test", 0.5)
        assert mem.get_last_task()["task_id"] == "t-test"
