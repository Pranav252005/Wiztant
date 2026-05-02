"""platforms/linux/hotkeys.py — Linux hotkey registration implementing BaseHotkeys."""
from __future__ import annotations

import threading
from typing import Callable, Dict, Set

from platforms.abstract import BaseHotkeys


class LinuxHotkeys(BaseHotkeys):
    """Linux global hotkeys via pynput (X11) or Electron WebSocket shortcuts."""

    def __init__(self):
        self._listener = None
        self._callbacks: Dict[str, Callable] = {}
        self._pressed: Set = set()
        self._last_press_time: Dict[str, float] = {}
        self._debounce_sec = 0.15

    # ── BaseHotkeys interface ─────────────────────────────────────────────────

    def register(self, shortcut: str, callback: Callable) -> bool:
        """Register a shortcut string like 'f9' or 'ctrl+space'."""
        self._callbacks[shortcut.lower().strip()] = callback
        return True

    def unregister(self, shortcut: str) -> bool:
        key = shortcut.lower().strip()
        if key in self._callbacks:
            del self._callbacks[key]
            return True
        return False

    def listen(self) -> None:
        """Start the pynput listener (non-blocking thread)."""
        if self._listener is not None and self._listener.is_alive():
            return
        self._start_pynput_listener()

    def stop(self) -> None:
        """Stop the listener."""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _start_pynput_listener(self):
        try:
            from pynput import keyboard as pynput_kb
        except ImportError:
            print("[Hotkeys/Linux] pynput not installed — skipping keyboard fallback")
            return

        def on_press(key):
            self._pressed.add(key)
            shortcut = self._key_to_shortcut(key)
            if shortcut and shortcut in self._callbacks:
                # Debounce: ignore Linux key-repeat events (common on X11/Wayland).
                import time as _time
                now = _time.time()
                last = self._last_press_time.get(shortcut, 0)
                if now - last < self._debounce_sec:
                    return
                self._last_press_time[shortcut] = now
                cb = self._callbacks[shortcut]
                threading.Thread(target=cb, daemon=True).start()
            # Check combo shortcuts (ctrl+space, etc.)
            for combo, cb in self._callbacks.items():
                if "+" in combo and self._combo_active(combo):
                    # Debounce combo shortcuts too.
                    import time as _time
                    now = _time.time()
                    last = self._last_press_time.get(combo, 0)
                    if now - last < self._debounce_sec:
                        continue
                    self._last_press_time[combo] = now
                    threading.Thread(target=cb, daemon=True).start()

        def on_release(key):
            self._pressed.discard(key)

        self._listener = pynput_kb.Listener(on_press=on_press, on_release=on_release)
        self._listener.daemon = True
        self._listener.start()
        print("[Hotkeys/Linux] pynput listener active")

    def _key_to_shortcut(self, key) -> str | None:
        from pynput.keyboard import Key
        mapping = {
            Key.f9: "f9",
            Key.f10: "f10",
            Key.esc: "escape",
            Key.space: "space",
        }
        return mapping.get(key)

    def _combo_active(self, combo: str) -> bool:
        parts = [p.strip().lower() for p in combo.split("+")]
        from pynput.keyboard import Key
        mod_map = {
            "ctrl": {Key.ctrl_l, Key.ctrl_r},
            "alt": {Key.alt_l, Key.alt_r},
            "shift": {Key.shift_l, Key.shift_r},
            "super": {Key.cmd_l, Key.cmd_r},
        }
        for part in parts:
            if part in mod_map:
                if not self._pressed & mod_map[part]:
                    return False
            else:
                # Non-modifier part must be pressed
                # Simplified: we only check on key press events
                pass
        return True

    # ── Legacy compatibility ──────────────────────────────────────────────────

    def register_hotkeys(self) -> None:
        """Backward-compatible entry point used by legacy main.py."""
        print("[Hotkeys/Linux] Using Electron global shortcuts + pynput fallback.")
        self.listen()
