"""Warp terminal adapter — stages commands, stops before Enter."""

from __future__ import annotations

from typing import Any, Dict

from core.agent_v2.adapters.base import ToolAdapter


class WarpAdapter(ToolAdapter):
    name = "warp"

    def is_available(self) -> bool:
        return True

    async def stage(self, action: Dict[str, Any]) -> Dict[str, Any]:
        command = action.get("value", "")
        if not command:
            return {"staged": False, "error": "empty command"}
        return {"staged": True, "tool": "warp", "command": command, "note": "User must press Enter in Warp"}
