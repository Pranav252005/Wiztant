"""platforms/windows/hotkeys.py — Windows hotkey registration implementing BaseHotkeys."""
from __future__ import annotations

import threading
from typing import Callable

from platforms.abstract import BaseHotkeys


class WindowsHotkeys(BaseHotkeys):
    """Windows global hotkeys via the `keyboard` library."""

    def __init__(self):
        self._callbacks: dict[str, Callable] = {}
        self._listener = None

    def register(self, shortcut: str, callback: Callable) -> bool:
        """Register a global shortcut."""
        try:
            import keyboard
            keyboard.add_hotkey(shortcut, callback, suppress=False, trigger_on_release=False)
            self._callbacks[shortcut.lower().strip()] = callback
            return True
        except Exception as e:
            print(f"[Hotkeys/Windows] Failed to register {shortcut}: {e}")
            return False

    def unregister(self, shortcut: str) -> bool:
        key = shortcut.lower().strip()
        if key in self._callbacks:
            try:
                import keyboard
                keyboard.remove_hotkey(shortcut)
            except Exception:
                pass
            del self._callbacks[key]
            return True
        return False

    def listen(self) -> None:
        """On Windows, the keyboard library hotkeys are global; no listener thread needed."""
        pass

    def stop(self) -> None:
        try:
            import keyboard
            for shortcut in list(self._callbacks.keys()):
                try:
                    keyboard.remove_hotkey(shortcut)
                except Exception:
                    pass
            self._callbacks.clear()
        except Exception:
            pass

    # ── Legacy compatibility ──────────────────────────────────────────────────

    def register_hotkeys(self) -> None:
        """Backward-compatible entry point. Registers defaults if not already set."""
        print("[Hotkeys/Windows] Registering global hotkeys via keyboard library")
