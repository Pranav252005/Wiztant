"""
Whiztant core/agent_isolation.py — Win32 input isolation for background agent windows.

Sends mouse clicks, keyboard input, and scroll events directly to a target window
via PostMessage/SendMessage WITHOUT moving the user's visible cursor or stealing
foreground focus. This is the key to non-blocking background agent execution.

Requires: pywin32 (win32gui, win32con, win32api, win32process)
"""

import os
import time
import asyncio
import ctypes
import ctypes.wintypes
from typing import Tuple, Optional

# Win32 constants (avoid import-time failure if pywin32 is missing)
try:
    import win32gui
    import win32con
    import win32api
    import win32process
    _WIN32_AVAILABLE = True
except ImportError:
    _WIN32_AVAILABLE = False
    print("[agent_isolation] pywin32 not installed — background agent input isolation unavailable")


# ── Win32 message constants ──────────────────────────────────────────────────

WM_LBUTTONDOWN   = 0x0201
WM_LBUTTONUP     = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONDOWN   = 0x0204
WM_RBUTTONUP     = 0x0205
WM_KEYDOWN       = 0x0100
WM_KEYUP         = 0x0101
WM_CHAR          = 0x0102
WM_MOUSEWHEEL    = 0x020A
MK_LBUTTON       = 0x0001

# Virtual key codes for common keys
VK_MAP = {
    "enter":     0x0D,
    "return":    0x0D,
    "tab":       0x09,
    "escape":    0x1B,
    "esc":       0x1B,
    "backspace": 0x08,
    "delete":    0x2E,
    "space":     0x20,
    "up":        0x26,
    "down":      0x28,
    "left":      0x25,
    "right":     0x27,
    "home":      0x24,
    "end":       0x23,
    "pageup":    0x21,
    "pagedown":  0x22,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "ctrl":  0x11,
    "shift": 0x10,
    "alt":   0x12,
}


def _require_win32():
    if not _WIN32_AVAILABLE:
        raise RuntimeError("pywin32 is required for background agent input isolation")


def _make_lparam(x: int, y: int) -> int:
    """Pack (x, y) into a single LPARAM for window messages."""
    return (y & 0xFFFF) << 16 | (x & 0xFFFF)


def _screen_to_client(hwnd: int, x: int, y: int) -> Tuple[int, int]:
    """Convert screen coordinates to window-client coordinates."""
    _require_win32()
    rect = win32gui.GetWindowRect(hwnd)
    client_x = x - rect[0]
    client_y = y - rect[1]
    return max(0, client_x), max(0, client_y)


def get_window_rect(hwnd: int) -> Tuple[int, int, int, int]:
    """Return (left, top, right, bottom) of a window in screen pixels."""
    _require_win32()
    return win32gui.GetWindowRect(hwnd)


def get_window_size(hwnd: int) -> Tuple[int, int]:
    """Return (width, height) of a window."""
    rect = get_window_rect(hwnd)
    return rect[2] - rect[0], rect[3] - rect[1]


def is_window_valid(hwnd: int) -> bool:
    """Check if a window handle is still valid and visible."""
    _require_win32()
    return bool(win32gui.IsWindow(hwnd))


# ── Input isolation context ──────────────────────────────────────────────────

class AgentInputContext:
    """
    Isolated input context for a background agent window.
    All input is sent via PostMessage so the user's foreground window,
    cursor position, and keyboard state are never affected.
    """

    def __init__(self, target_window_handle: int):
        _require_win32()
        self.target_hwnd = target_window_handle
        self._original_foreground: Optional[int] = None

    def _save_foreground(self):
        """Remember the user's current foreground window."""
        try:
            self._original_foreground = win32gui.GetForegroundWindow()
        except Exception:
            self._original_foreground = None

    def _restore_foreground(self):
        """Restore the user's foreground window if it was displaced."""
        if self._original_foreground and win32gui.IsWindow(self._original_foreground):
            try:
                fg = win32gui.GetForegroundWindow()
                if fg != self._original_foreground:
                    win32gui.SetForegroundWindow(self._original_foreground)
            except Exception:
                pass

    # ── Click ────────────────────────────────────────────────────────────────

    async def click_in_window(self, x: int, y: int):
        """
        Click at (x, y) in window-client coordinates via PostMessage.
        Does NOT move the user's visible mouse cursor.
        """
        lparam = _make_lparam(x, y)

        win32gui.PostMessage(self.target_hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
        await asyncio.sleep(0.08)
        win32gui.PostMessage(self.target_hwnd, WM_LBUTTONUP, 0, lparam)
        await asyncio.sleep(0.05)

    async def double_click_in_window(self, x: int, y: int):
        """Double-click via PostMessage."""
        lparam = _make_lparam(x, y)

        win32gui.PostMessage(self.target_hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
        await asyncio.sleep(0.04)
        win32gui.PostMessage(self.target_hwnd, WM_LBUTTONUP, 0, lparam)
        await asyncio.sleep(0.04)
        win32gui.PostMessage(self.target_hwnd, WM_LBUTTONDBLCLK, MK_LBUTTON, lparam)
        await asyncio.sleep(0.04)
        win32gui.PostMessage(self.target_hwnd, WM_LBUTTONUP, 0, lparam)
        await asyncio.sleep(0.05)

    async def right_click_in_window(self, x: int, y: int):
        """Right-click via PostMessage."""
        lparam = _make_lparam(x, y)

        win32gui.PostMessage(self.target_hwnd, WM_RBUTTONDOWN, MK_LBUTTON, lparam)
        await asyncio.sleep(0.08)
        win32gui.PostMessage(self.target_hwnd, WM_RBUTTONUP, 0, lparam)
        await asyncio.sleep(0.05)

    # ── Typing ───────────────────────────────────────────────────────────────

    async def type_text_in_window(self, text: str, char_delay: float = 0.03):
        """
        Type text character-by-character via WM_CHAR.
        Does NOT steal keyboard focus from the user's foreground app.
        """
        for ch in text:
            win32gui.PostMessage(self.target_hwnd, WM_CHAR, ord(ch), 0)
            await asyncio.sleep(char_delay)

    # ── Key press ────────────────────────────────────────────────────────────

    async def press_key_in_window(self, key_name: str):
        """
        Press a single key or key combo (e.g. 'enter', 'ctrl+a', 'ctrl+shift+t').
        Modifiers are held via KEYDOWN, the main key is pressed, then modifiers are released.
        """
        parts = [k.strip().lower() for k in key_name.replace("+", " ").split() if k.strip()]
        if not parts:
            return

        modifiers = []
        main_keys = []
        for p in parts:
            if p in ("ctrl", "shift", "alt"):
                modifiers.append(VK_MAP[p])
            else:
                vk = VK_MAP.get(p)
                if vk is not None:
                    main_keys.append(vk)
                elif len(p) == 1:
                    # Single character — use VkKeyScan
                    main_keys.append(ord(p.upper()))
                else:
                    print(f"[agent_isolation] Unknown key: {p}")
                    return

        # Press modifiers
        for vk in modifiers:
            win32gui.PostMessage(self.target_hwnd, WM_KEYDOWN, vk, 0)
            await asyncio.sleep(0.02)

        # Press and release main keys
        for vk in main_keys:
            win32gui.PostMessage(self.target_hwnd, WM_KEYDOWN, vk, 0)
            await asyncio.sleep(0.04)
            win32gui.PostMessage(self.target_hwnd, WM_KEYUP, vk, 0)
            await asyncio.sleep(0.02)

        # Release modifiers (reverse order)
        for vk in reversed(modifiers):
            win32gui.PostMessage(self.target_hwnd, WM_KEYUP, vk, 0)
            await asyncio.sleep(0.02)

    # ── Scroll ───────────────────────────────────────────────────────────────

    async def scroll_in_window(self, x: int, y: int, direction: str = "down", amount: int = 3):
        """
        Scroll inside the agent window via WM_MOUSEWHEEL.
        direction: 'up' or 'down'
        amount: number of scroll notches
        """
        lparam = _make_lparam(x, y)
        delta = 120 * amount
        if direction == "down":
            delta = -delta
        wparam = (delta & 0xFFFF) << 16
        win32gui.PostMessage(self.target_hwnd, WM_MOUSEWHEEL, wparam, lparam)
        await asyncio.sleep(0.1)


# ── Window enumeration helpers ───────────────────────────────────────────────

def find_window_by_pid(pid: int) -> Optional[int]:
    """Find the main window handle for a given process ID."""
    _require_win32()
    result = []

    def _enum_callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
        if found_pid == pid:
            result.append(hwnd)
        return True

    win32gui.EnumWindows(_enum_callback, None)
    return result[0] if result else None


def find_windows_by_pid(pid: int) -> list:
    """Find ALL window handles for a given process ID."""
    _require_win32()
    result = []

    def _enum_callback(hwnd, _):
        _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
        if found_pid == pid:
            result.append(hwnd)
        return True

    win32gui.EnumWindows(_enum_callback, None)
    return result


def minimize_window(hwnd: int):
    """Minimize a window without stealing focus."""
    _require_win32()
    win32gui.ShowWindow(hwnd, 6)  # SW_MINIMIZE


def restore_window(hwnd: int):
    """Restore a minimized window without activating it."""
    _require_win32()
    # SW_SHOWNOACTIVATE = 4
    win32gui.ShowWindow(hwnd, 4)


def get_foreground_window() -> int:
    """Return the current foreground window handle."""
    _require_win32()
    return win32gui.GetForegroundWindow()
