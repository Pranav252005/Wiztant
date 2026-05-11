"""Cursor IDE adapter — stages prompts in chat, stops before Enter."""

from __future__ import annotations

from typing import Any, Dict

from core.agent_v2.adapters.base import ToolAdapter


class CursorAdapter(ToolAdapter):
    name = "cursor"

    def is_available(self) -> bool:
        return True

    async def stage(self, action: Dict[str, Any]) -> Dict[str, Any]:
        prompt = action.get("value", "")
        if not prompt:
            return {"staged": False, "error": "empty prompt"}
        return {"staged": True, "tool": "cursor", "prompt": prompt, "note": "User must press Enter in Cursor"}
