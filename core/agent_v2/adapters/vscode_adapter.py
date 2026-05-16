"""
VS Code adapter — finds VS Code window, opens Copilot/Chat panel,
clears input, and types the optimized prompt. Stops before Enter.
"""

from __future__ import annotations

import time
from typing import Any, Dict

from core.agent_v2.adapters.base import ToolAdapter


class VSCodeAdapter(ToolAdapter):
    name = "vscode"

    _WINDOW_TITLES = ["Visual Studio Code", "Code", "code"]
    _CHAT_SHORTCUT = ("ctrl", "shift", "i")
    _CHAT_SHORTCUT_ALT = ("ctrl", "alt", "i")

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

        # 1. Find and focus VS Code window
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
                "error": "VS Code window not found. Please open VS Code.",
                "tool": "vscode",
            }

        ok, msg = runtime.focus_window_by_title(found_title)
        if not ok:
            return {"staged": False, "error": msg, "tool": "vscode"}

        time.sleep(0.3)

        # 2. Open Copilot / Chat panel
        ok, msg = runtime.hotkey(*self._CHAT_SHORTCUT)
        if not ok:
            ok, msg = runtime.hotkey(*self._CHAT_SHORTCUT_ALT)
        if not ok:
            return {"staged": False, "error": f"Could not open chat panel: {msg}", "tool": "vscode"}

        time.sleep(0.5)

        # 3. Clear input
        runtime.clear_input_field()
        time.sleep(0.2)

        # 4. Type prompt
        ok, msg = runtime.type_text(prompt, interval=0.005)
        if not ok:
            return {"staged": False, "error": f"Failed to type: {msg}", "tool": "vscode"}

        return {
            "staged": True,
            "tool": "vscode",
            "prompt": prompt,
            "note": "Prompt is staged in VS Code's Copilot/Chat panel. Review and press Enter to execute.",
            "auto_executed": False,
        }
