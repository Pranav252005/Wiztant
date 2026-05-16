"""
Cursor IDE adapter — finds Cursor window, opens AI chat panel,
clears input, and types the optimized prompt. Stops before Enter.
"""

from __future__ import annotations

import time
from typing import Any, Dict

from core.agent_v2.adapters.base import ToolAdapter


class CursorAdapter(ToolAdapter):
    name = "cursor"

    # Window title substrings to search for
    _WINDOW_TITLES = ["Cursor", "Cursor - ", "cursor"]
    # Shortcut to open AI chat panel (Cmd/Ctrl + L)
    _CHAT_SHORTCUT = ("ctrl", "l")
    # Alternative shortcut
    _CHAT_SHORTCUT_ALT = ("ctrl", "shift", "l")

    def is_available(self) -> bool:
        runtime = self._get_runtime()
        for title in self._WINDOW_TITLES:
            if runtime.find_window_by_title(title):
                return True
        return False

    async def stage(self, action: Dict[str, Any]) -> Dict[str, Any]:
        prompt = action.get("value", "")
        if not prompt:
            return {"staged": False, "error": "empty prompt"}

        runtime = self._get_runtime()

        # 1. Find and focus Cursor window
        hwnd = None
        found_title = ""
        for title in self._WINDOW_TITLES:
            hwnd = runtime.find_window_by_title(title)
            if hwnd:
                found_title = title
                break

        if not hwnd:
            return {
                "staged": False,
                "error": "Cursor window not found. Please open Cursor.",
                "tool": "cursor",
            }

        ok, msg = runtime.focus_window_by_title(found_title)
        if not ok:
            return {"staged": False, "error": msg, "tool": "cursor"}

        time.sleep(0.3)

        # 2. Open AI chat panel
        ok, msg = runtime.hotkey(*self._CHAT_SHORTCUT)
        if not ok:
            # Try alternative shortcut
            ok, msg = runtime.hotkey(*self._CHAT_SHORTCUT_ALT)
        if not ok:
            return {"staged": False, "error": f"Could not open chat panel: {msg}", "tool": "cursor"}

        time.sleep(0.5)

        # 3. Clear existing input
        ok, msg = runtime.clear_input_field()
        if not ok:
            # Fallback: select all + type replaces selection
            pass

        time.sleep(0.2)

        # 4. Type the prompt (staged — DO NOT press Enter)
        ok, msg = runtime.type_text(prompt, interval=0.005)
        if not ok:
            return {"staged": False, "error": f"Failed to type prompt: {msg}", "tool": "cursor"}

        return {
            "staged": True,
            "tool": "cursor",
            "prompt": prompt,
            "note": "Prompt is staged in Cursor's AI chat panel. Review and press Enter to execute.",
            "auto_executed": False,
        }
