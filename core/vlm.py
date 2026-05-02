"""
core/vlm.py — Cross-platform compatibility shim for legacy consumers.

On Linux delegates agent tasks to platforms.linux._vlm_impl
and input actions to core.platform_backends.
On Windows this file should be replaced by the full platforms/windows/_vlm_impl
re-export (or the original core/vlm.py restored).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Optional, Tuple

import core as state
from core.platform_backends import (
    click,
    cursor_position,
    list_monitors,
    screen_size,
    screenshot,
    type_text,
    press_key,
)

# Agent entry points — Linux uses the dedicated Linux implementation
from platforms.linux._vlm_impl import (
    run_agent_loop,
    run_agent_task,
    run_agent_task_async,
)

# ══════════════════════════════════════════════════════════════════════════════
# PyAutoGUI compatibility layer (Linux: pyautogui unavailable, degrade gracefully)
# ══════════════════════════════════════════════════════════════════════════════

def _pyautogui():
    """Return pyautogui module or None so tools degrade gracefully."""
    return None


def _safe_pyautogui_call(fn: Callable[[], Any]) -> Optional[str]:
    """Wrap a pyautogui call; on Linux always returns an error string."""
    try:
        fn()
        return None
    except Exception as e:
        return str(e)


def _list_monitors():
    """Return list of monitor dicts (delegates to platform backends)."""
    return list_monitors()


def _coerce_display_index(display) -> int:
    monitors = _list_monitors()
    total = max(1, len(monitors))
    try:
        index = int(display) if display is not None else 1
    except Exception:
        index = 1
    return min(max(index, 1), total)


def _display_bounds(display: int) -> Tuple[int, int, int, int]:
    monitors = _list_monitors()
    if not monitors:
        w, h = screen_size()
        return 0, 0, w, h
    idx = _coerce_display_index(display) - 1
    try:
        m = monitors[idx]
        return (
            int(m.get("left", 0)),
            int(m.get("top", 0)),
            int(m.get("width", 0)),
            int(m.get("height", 0)),
        )
    except Exception:
        w, h = screen_size()
        return 0, 0, w, h


def _current_cursor_display() -> int:
    try:
        x_pos, y_pos = cursor_position()
    except Exception:
        x_pos, y_pos = 0, 0
    monitors = _list_monitors()
    for i, m in enumerate(monitors, start=1):
        left = int(m.get("left", 0))
        top = int(m.get("top", 0))
        width = int(m.get("width", 0))
        height = int(m.get("height", 0))
        if left <= x_pos < left + width and top <= y_pos < top + height:
            return i
    return 1


def _xy_for_display(display: int, x: float, y: float) -> Optional[Tuple[int, int]]:
    left, top, width, height = _display_bounds(display)
    if width <= 0 or height <= 0:
        return None
    try:
        x_norm = float(x)
        y_norm = float(y)
    except Exception:
        return None
    return int(left + x_norm * width), int(top + y_norm * height)


def _run_screenshot_capture_once() -> list[str]:
    target_dir = Path(state.SCREENSHOT_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    img = screenshot()
    fmt = state.SCREENSHOT_FILENAME_FMT
    path = target_dir / fmt.format(index=1)
    img.save(str(path), format="PNG")
    paths.append(str(path))
    return paths


# ══════════════════════════════════════════════════════════════════════════════
# Safe input helpers (used by background_agent)
# ══════════════════════════════════════════════════════════════════════════════

def safe_click(x: int, y: int, _reason: str = "") -> bool:
    success, _ = click(x, y)
    return success


def safe_type(text: str, _reason: str = "") -> bool:
    success, _ = type_text(text, interval=0.02)
    return success


def safe_press(key: str, _reason: str = "") -> bool:
    success, _ = press_key(key)
    return success


__all__ = [
    "run_agent_loop",
    "run_agent_task",
    "run_agent_task_async",
    "_pyautogui",
    "_safe_pyautogui_call",
    "_coerce_display_index",
    "_current_cursor_display",
    "_display_bounds",
    "_xy_for_display",
    "_run_screenshot_capture_once",
    "safe_click",
    "safe_type",
    "safe_press",
]
