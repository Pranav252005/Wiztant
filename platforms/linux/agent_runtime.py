"""platforms/linux/agent_runtime.py — Linux agent runtime (hands).

Uses mss for screenshots and delegates input to LinuxSystemAccess
(xdotool / pynput / wtype / ydotool with automatic fallback).
"""
from __future__ import annotations

import logging
import os
import shutil
from typing import Tuple

from PIL import Image

from platforms.abstract.base_agent_runtime import BaseAgentRuntime

log = logging.getLogger("platforms.linux.agent_runtime")


class LinuxAgentRuntime(BaseAgentRuntime):
    """Linux desktop I/O for the unified agent."""

    def __init__(self):
        self._system = None
        self._check_backends()

    def _sys(self):
        """Lazy-load LinuxSystemAccess."""
        if self._system is None:
            from platforms.linux.system_access import LinuxSystemAccess
            self._system = LinuxSystemAccess()
        return self._system

    # ── Backend pre-flight ────────────────────────────────────────────────────

    def _check_backends(self) -> None:
        """Warn if critical backends are missing."""
        if not os.getenv("DISPLAY") and not os.getenv("WAYLAND_DISPLAY"):
            log.warning(
                "No display detected (DISPLAY or WAYLAND_DISPLAY not set). "
                "Screenshots and window management will fail."
            )
        session = os.environ.get("XDG_SESSION_TYPE", "").lower()
        is_wayland = session == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY"))

        if is_wayland:
            if not shutil.which("wtype") and not shutil.which("ydotool"):
                log.warning(
                    "Wayland detected but neither wtype nor ydotool is installed. "
                    "Typing and hotkeys may fail. Install wtype (preferred) or ydotool."
                )
        else:
            if not shutil.which("xdotool"):
                log.warning(
                    "X11 detected but xdotool is not installed. "
                    "Typing, hotkeys, and window management may fail."
                )

    # ── Screenshot ────────────────────────────────────────────────────────────

    def screenshot(self) -> Image.Image:
        return self._sys().take_screenshot()

    # ── Mouse ─────────────────────────────────────────────────────────────────

    def click(self, x: int, y: int, button: str = "left") -> Tuple[bool, str]:
        return self._sys().click(x, y, button=button, clicks=1)

    def move(self, x: int, y: int) -> Tuple[bool, str]:
        return self._sys().move(x, y)

    def scroll(self, x: int, y: int, amount: int) -> Tuple[bool, str]:
        return self._sys().scroll(x, y, amount)

    # ── Keyboard ──────────────────────────────────────────────────────────────

    def type_text(self, text: str, interval: float = 0.01) -> Tuple[bool, str]:
        return self._sys().type_text(text)

    def press_key(self, key: str) -> Tuple[bool, str]:
        return self._sys().press_key(key)

    def hotkey(self, *keys: str) -> Tuple[bool, str]:
        return self._sys().hotkey(*keys)

    # ── App / Window ──────────────────────────────────────────────────────────

    def open_app(self, name: str) -> str:
        return self._sys().launch_app(name)

    def open_browser(self, name: str, url: str | None = None, profile: str | None = None) -> str:
        return self._sys().launch_browser(name, url=url, profile=profile)

    def ensure_app_open(self, name: str, url: str | None = None, profile: str | None = None) -> str:
        return self._sys().ensure_app_open(name, url=url, profile=profile)

    def get_browser_profiles(self, browser_name: str) -> list[str]:
        return self._sys()._get_chrome_profiles(browser_name)

    def get_foreground_app(self) -> str:
        return self._sys().get_foreground_app()

    # ── Window Finding & Focus ────────────────────────────────────────────────

    def find_window_by_title(self, substring: str) -> Optional[str]:
        """Find a window whose title contains substring. Returns window ID or None."""
        try:
            result = subprocess.run(
                ["xdotool", "search", "--name", substring],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().splitlines()
                return lines[0].strip() if lines else None
        except Exception:
            pass
        # Fallback: wmctrl list + manual match
        try:
            result = subprocess.run(
                ["wmctrl", "-l"], capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    parts = line.split(None, 3)
                    if len(parts) >= 4 and substring.lower() in parts[3].lower():
                        return parts[0]
        except Exception:
            pass
        return None

    def focus_window_by_title(self, substring: str) -> Tuple[bool, str]:
        """Find and focus a window by title substring."""
        wid = self.find_window_by_title(substring)
        if not wid:
            return False, f"window_not_found:{substring}"
        try:
            subprocess.run(
                ["xdotool", "windowactivate", "--sync", wid],
                capture_output=True, timeout=5,
            )
            return True, f"focused_window:{wid}"
        except Exception as e:
            return False, f"focus_failed:{e}"

    def clear_input_field(self) -> Tuple[bool, str]:
        """Clear focused input via Ctrl+A + Delete."""
        try:
            self.hotkey("ctrl", "a")
            self.press_key("delete")
            return True, "cleared_input"
        except Exception as e:
            return False, f"clear_failed:{e}"

    # ── Display / Cursor ──────────────────────────────────────────────────────

    def screen_size(self) -> Tuple[int, int]:
        return self._sys().screen_size()

    def cursor_position(self) -> Tuple[int, int]:
        return self._sys().cursor_position()
