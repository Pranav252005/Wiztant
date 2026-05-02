"""Platform Abstraction Layer (PAL) — Abstract Base Classes for Whiztant."""
from __future__ import annotations

import abc
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image

# Re-export agent runtime base for convenience
from platforms.abstract.base_agent_runtime import BaseAgentRuntime


class BaseHotkeys(abc.ABC):
    """Global hotkey registration and keyboard event listening."""

    @abc.abstractmethod
    def register(self, shortcut: str, callback: callable) -> bool:
        """Register a global shortcut (e.g. 'f9', 'ctrl+space')."""

    @abc.abstractmethod
    def unregister(self, shortcut: str) -> bool:
        """Unregister a previously registered shortcut."""

    @abc.abstractmethod
    def listen(self) -> None:
        """Start listening for hotkey events (blocking or non-blocking)."""

    @abc.abstractmethod
    def stop(self) -> None:
        """Stop listening and clean up."""


class BaseTTS(abc.ABC):
    """Text-to-speech engine interface."""

    @abc.abstractmethod
    def speak(self, text: str, voice: str | None = None, blocking: bool = False) -> None:
        """Speak the given text."""

    @abc.abstractmethod
    def stop(self) -> None:
        """Stop any active speech."""

    @abc.abstractmethod
    def is_speaking(self) -> bool:
        """Return True if currently speaking."""


class BaseVLM(abc.ABC):
    """Vision-Language Model / Agent backend interface."""

    @abc.abstractmethod
    def capture(self) -> Image.Image:
        """Capture a screenshot and return it as a PIL Image."""

    @abc.abstractmethod
    def analyze(self, prompt: str, image: Image.Image) -> dict:
        """Analyze the image with the given prompt, return structured result."""

    @abc.abstractmethod
    def get_capabilities(self) -> dict:
        """Return backend capabilities dict."""

    @abc.abstractmethod
    def run_agent_loop(
        self,
        task: str,
        toast: callable | None = None,
        progress_cb: callable | None = None,
    ) -> str:
        """Execute an agent task loop. Returns result message."""


class BaseWindowMgmt(abc.ABC):
    """Window management and overlay creation."""

    @abc.abstractmethod
    def get_active_window(self) -> dict:
        """Return info about the currently focused window."""

    @abc.abstractmethod
    def list_windows(self) -> List[Tuple[str, Any]]:
        """Return list of (title, window_id) tuples for visible windows."""

    @abc.abstractmethod
    def focus_window(self, window_id: Any) -> bool:
        """Raise and focus the given window."""

    @abc.abstractmethod
    def get_window_bounds(self, window_id: Any) -> Tuple[int, int, int, int]:
        """Return (x, y, w, h) for the given window."""

    @abc.abstractmethod
    def create_overlay(self, width: int, height: int) -> Any:
        """Create a platform-specific overlay handle (e.g. HWND or X11 window)."""

    @abc.abstractmethod
    def minimize_window(self) -> None:
        """Minimize the currently active window."""

    @abc.abstractmethod
    def open_file(self, path: str) -> None:
        """Open a file with the default application."""

    @abc.abstractmethod
    def get_window_class_name(self) -> str:
        """Return the class name of the active window."""


class BaseSystemAccess(abc.ABC):
    """Low-level system access: input, screenshots, clipboard, process execution."""

    @abc.abstractmethod
    def execute(self, command: str | List[str]) -> Tuple[bool, str]:
        """Execute a shell command, return (success, message)."""

    @abc.abstractmethod
    def get_clipboard(self) -> str:
        """Return current clipboard text."""

    @abc.abstractmethod
    def set_clipboard(self, text: str) -> None:
        """Set clipboard text."""

    @abc.abstractmethod
    def take_screenshot(self) -> Image.Image:
        """Return a full-screen PIL RGB screenshot."""

    @abc.abstractmethod
    def click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> Tuple[bool, str]:
        """Click at screen coordinates."""

    @abc.abstractmethod
    def move(self, x: int, y: int) -> Tuple[bool, str]:
        """Move the mouse cursor."""

    @abc.abstractmethod
    def scroll(self, x: int, y: int, amount: int) -> Tuple[bool, str]:
        """Scroll at screen coordinates."""

    @abc.abstractmethod
    def type_text(self, text: str, interval: float = 0.01) -> Tuple[bool, str]:
        """Type the given text."""

    @abc.abstractmethod
    def press_key(self, key: str) -> Tuple[bool, str]:
        """Press a single key."""

    @abc.abstractmethod
    def hotkey(self, *keys: str) -> Tuple[bool, str]:
        """Press a key combination."""

    @abc.abstractmethod
    def launch_app(self, app_name: str) -> str:
        """Launch an application by name."""

    @abc.abstractmethod
    def launch_browser(self, name: str, url: Optional[str] = None, profile: Optional[str] = None) -> str:
        """Launch a browser with optional URL and profile."""

    @abc.abstractmethod
    def ensure_app_open(self, app_name: str, url: Optional[str] = None, profile: Optional[str] = None) -> str:
        """Ensure an app is open and focused; launch if needed."""

    @abc.abstractmethod
    def list_monitors(self) -> List[dict]:
        """Return list of monitor dicts."""

    @abc.abstractmethod
    def screen_size(self) -> Tuple[int, int]:
        """Return (width, height) of the primary screen."""

    @abc.abstractmethod
    def cursor_position(self) -> Tuple[int, int]:
        """Return current mouse cursor position."""

    @abc.abstractmethod
    def raise_window(self, window_id: Any) -> bool:
        """Raise a window to the foreground."""

    @abc.abstractmethod
    def get_foreground_app(self) -> str:
        """Return the title/class of the foreground application."""

    @abc.abstractmethod
    def open_file(self, path: str) -> None:
        """Open a file with the default application."""

    @abc.abstractmethod
    def open_browser(self, url: str, profile: str | None = None) -> bool:
        """Open a URL in the default or requested browser. Return success."""
