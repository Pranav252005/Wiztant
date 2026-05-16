"""
Windsurf IDE adapter — finds Windsurf window, opens Cascade chat,
clears input, and types the optimized prompt. Stops before Enter.
"""

from __future__ import annotations

import time
from typing import Any, Dict

from core.agent_v2.adapters.base import ToolAdapter


class WindsurfAdapter(ToolAdapter):
    name = "windsurf"

    _WINDOW_TITLES = ["Windsurf", "windsurf", "Codeium"]
    _CHAT_SHORTCUT = ("ctrl", "shift", "l")
    _CHAT_SHORTCUT_ALT = ("ctrl", "i")

    def is_available(self) -> bool:
        runtime = self._get_runtime()
        for title in self._WINDOW_TITLES:
            if runtime.find_window_by_title(title):
                return True
        return False

    async def stage(self, action: Dict[str, Any]) -> Dict[str, Any]:
        command = action.get("value", "")
        if not command:
            return {"staged": False, "error": "empty command"}

        runtime = self._get_runtime()

        # 1. Find and focus Windsurf window
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
                "error": "Windsurf window not found. Please open Windsurf.",
                "tool": "windsurf",
            }

        ok, msg = runtime.focus_window_by_title(found_title)
        if not ok:
            return {"staged": False, "error": msg, "tool": "windsurf"}

        time.sleep(0.3)

        # 2. Open Cascade chat
        ok, msg = runtime.hotkey(*self._CHAT_SHORTCUT)
        if not ok:
            ok, msg = runtime.hotkey(*self._CHAT_SHORTCUT_ALT)
        if not ok:
            return {"staged": False, "error": f"Could not open Cascade: {msg}", "tool": "windsurf"}

        time.sleep(0.5)

        # 3. Clear input
        runtime.clear_input_field()
        time.sleep(0.2)

        # 4. Type prompt
        ok, msg = runtime.type_text(command, interval=0.005)
        if not ok:
            return {"staged": False, "error": f"Failed to type: {msg}", "tool": "windsurf"}

        return {
            "staged": True,
            "tool": "windsurf",
            "command": command,
            "note": "Command is staged in Windsurf's Cascade chat. Review and press Enter to execute.",
            "auto_executed": False,
        }
