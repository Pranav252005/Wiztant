"""platforms/windows/agent_runtime.py — Windows agent runtime (hands).

Uses pyautogui for screenshots, clicks, typing, and scroll.
Delegates app/window management to WindowsSystemAccess.
"""
from __future__ import annotations

import logging
from typing import Tuple

from PIL import Image

from platforms.abstract.base_agent_runtime import BaseAgentRuntime

log = logging.getLogger("platforms.windows.agent_runtime")


class WindowsAgentRuntime(BaseAgentRuntime):
    """Windows desktop I/O for the unified agent."""

    def __init__(self):
        self._system = None
        self._pyautogui = None

    def _sys(self):
        """Lazy-load WindowsSystemAccess."""
        if self._system is None:
            from platforms.windows.system_access import WindowsSystemAccess
            self._system = WindowsSystemAccess()
        return self._system

    def _pg(self):
        """Lazy-load pyautogui."""
        if self._pyautogui is None:
            import pyautogui
            self._pyautogui = pyautogui
        return self._pyautogui

    # ── Screenshot ────────────────────────────────────────────────────────────

    def screenshot(self) -> Image.Image:
        return self._pg().screenshot()

    # ── Mouse ─────────────────────────────────────────────────────────────────

    def click(self, x: int, y: int, button: str = "left") -> Tuple[bool, str]:
        try:
            self._pg().click(x, y, button=button)
            return True, f"clicked at ({x}, {y})"
        except Exception as e:
            return False, f"click failed: {e}"

    def move(self, x: int, y: int) -> Tuple[bool, str]:
        try:
            self._pg().moveTo(x, y)
            return True, f"moved to ({x}, {y})"
        except Exception as e:
            return False, f"move failed: {e}"

    def scroll(self, x: int, y: int, amount: int) -> Tuple[bool, str]:
        try:
            self._pg().moveTo(x, y)
            self._pg().scroll(amount)
            return True, f"scrolled at ({x}, {y})"
        except Exception as e:
            return False, f"scroll failed: {e}"

    # ── Keyboard ──────────────────────────────────────────────────────────────

    def type_text(self, text: str, interval: float = 0.01) -> Tuple[bool, str]:
        try:
            self._pg().typewrite(text, interval=interval)
            return True, f"typed '{text[:50]}{'...' if len(text) > 50 else ''}'"
        except Exception as e:
            return False, f"type failed: {e}"

    def press_key(self, key: str) -> Tuple[bool, str]:
        try:
            self._pg().press(key)
            return True, f"pressed {key}"
        except Exception as e:
            return False, f"press failed: {e}"

    def hotkey(self, *keys: str) -> Tuple[bool, str]:
        try:
            self._pg().hotkey(*keys)
            return True, f"hotkey {'+'.join(keys)}"
        except Exception as e:
            return False, f"hotkey failed: {e}"

    # ── App / Window ──────────────────────────────────────────────────────────

    def open_app(self, name: str) -> str:
        return self._sys().launch_app(name)

    def open_browser(self, name: str, url: str | None = None, profile: str | None = None) -> str:
        return self._sys().launch_browser(name, url=url, profile=profile)

    def ensure_app_open(self, name: str, url: str | None = None, profile: str | None = None) -> str:
        return self._sys().ensure_app_open(name, url=url, profile=profile)

    def get_browser_profiles(self, browser_name: str) -> list[str]:
        return self._sys()._get_chrome_profiles_windows(browser_name)

    def get_foreground_app(self) -> str:
        return self._sys().get_foreground_app()

    # ── Window Finding & Focus ────────────────────────────────────────────────

    def find_window_by_title(self, substring: str) -> Optional[int]:
        """Find a window whose title contains substring. Returns hwnd or None."""
        try:
            import win32gui
            results: List[Tuple[str, int]] = []
            def _cb(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    t = win32gui.GetWindowText(hwnd) or ""
                    if substring.lower() in t.lower():
                        results.append((t, hwnd))
            win32gui.EnumWindows(_cb, None)
            return results[0][1] if results else None
        except Exception:
            return None

    def focus_window_by_title(self, substring: str) -> Tuple[bool, str]:
        """Find and focus a window by title substring."""
        hwnd = self.find_window_by_title(substring)
        if not hwnd:
            return False, f"window_not_found:{substring}"
        try:
            import win32gui, win32con
            placement = win32gui.GetWindowPlacement(hwnd)
            if placement[1] == win32con.SW_SHOWMINIMIZED:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.3)
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.4)
            return True, f"focused_window:{hwnd}"
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
