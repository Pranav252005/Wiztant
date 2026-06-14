"""Stub stager — old adapters archived. Three-Brain system uses core/agent_actions.py."""
from __future__ import annotations

from typing import Any, Dict, Optional


class Stager:
    """Minimal stub to prevent import errors in legacy plan_executor.py."""

    def __init__(self, tool_preferences: Optional[Dict[str, str]] = None) -> None:
        self.tool_preferences = tool_preferences or {}

    async def stage_subphase(self, tool: str, action: Dict[str, Any]) -> Dict[str, Any]:
        return {"staged": False, "error": "Legacy stager archived — use Three-Brain Agent"}
