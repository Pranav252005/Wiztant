"""platforms/abstract/base_agent_runtime.py — Abstract base for agent desktop runtimes.

The unified agent brain imports only this base + factory.get_agent_runtime().
Platform-specific implementations live in platforms/linux/agent_runtime.py and
platforms/windows/agent_runtime.py.
"""
from __future__ import annotations

import abc
from typing import List, Tuple

from PIL import Image


class BaseAgentRuntime(abc.ABC):
    """Desktop I/O runtime for the unified agent. Implements the 'hands'.

    The brain (core/agent_unified.py) calls these methods; the runtime handles
    all OS-specific APIs (mss/xdotool on Linux, pyautogui/win32 on Windows).
    """

    # ── Screenshot ────────────────────────────────────────────────────────────

    @abc.abstractmethod
    def screenshot(self) -> Image.Image:
        """Capture a full-screen RGB screenshot and return a PIL Image."""

    # ── Mouse ─────────────────────────────────────────────────────────────────

    @abc.abstractmethod
    def click(self, x: int, y: int, button: str = "left") -> Tuple[bool, str]:
        """Click at screen coordinates. Returns (success, message)."""

    @abc.abstractmethod
    def move(self, x: int, y: int) -> Tuple[bool, str]:
        """Move the cursor to screen coordinates. Returns (success, message)."""

    @abc.abstractmethod
    def scroll(self, x: int, y: int, amount: int) -> Tuple[bool, str]:
        """Scroll at screen coordinates. Positive = up, negative = down."""

    # ── Keyboard ──────────────────────────────────────────────────────────────

    @abc.abstractmethod
    def type_text(self, text: str, interval: float = 0.01) -> Tuple[bool, str]:
        """Type the given text. Returns (success, message)."""

    @abc.abstractmethod
    def press_key(self, key: str) -> Tuple[bool, str]:
        """Press a single key (e.g. 'enter', 'esc', 'f5')."""

    @abc.abstractmethod
    def hotkey(self, *keys: str) -> Tuple[bool, str]:
        """Press a key combination (e.g. hotkey('ctrl', 't'))."""

    # ── App / Window ──────────────────────────────────────────────────────────

    @abc.abstractmethod
    def open_app(self, name: str) -> str:
        """Launch or focus an application by friendly name. Returns a status message."""

    @abc.abstractmethod
    def open_browser(self, name: str, url: str | None = None, profile: str | None = None) -> str:
        """Launch a browser with an optional URL and profile. Returns a status message."""

    @abc.abstractmethod
    def ensure_app_open(self, name: str, url: str | None = None, profile: str | None = None) -> str:
        """Ensure an app is open and focused; launch if needed."""

    def get_browser_profiles(self, browser_name: str) -> List[str]:
        """Return available profile names for a browser. Override if supported."""
        return []

    @abc.abstractmethod
    def get_foreground_app(self) -> str:
        """Return the class name / title of the currently focused window."""

    # ── Display / Cursor ──────────────────────────────────────────────────────

    @abc.abstractmethod
    def screen_size(self) -> Tuple[int, int]:
        """Return (width, height) of the primary display."""

    @abc.abstractmethod
    def cursor_position(self) -> Tuple[int, int]:
        """Return current mouse cursor (x, y)."""
