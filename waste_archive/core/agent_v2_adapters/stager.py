"""
Stager: routes subphases to the correct adapter and enforces
'type but don't press Enter'.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.agent_v2.adapters.base import ToolAdapter
from core.agent_v2.adapters.auto_router import AutoRouter
from core.agent_v2.adapters.cursor_adapter import CursorAdapter
from core.agent_v2.adapters.windsurf_adapter import WindsurfAdapter
from core.agent_v2.adapters.vscode_adapter import VSCodeAdapter
from core.agent_v2.adapters.lovable_adapter import LovableAdapter


class Stager:
    """Orchestrates staging across multiple tool adapters."""

    def __init__(self, tool_preferences: Optional[Dict[str, str]] = None) -> None:
        self._adapters: Dict[str, ToolAdapter] = {
            "cursor": CursorAdapter(),
            "windsurf": WindsurfAdapter(),
            "vscode": VSCodeAdapter(),
            "lovable": LovableAdapter(),
        }
        self._router = AutoRouter(tool_preferences)

    def get_adapter(self, tool: str) -> ToolAdapter:
        adapter = self._adapters.get(tool)
        if not adapter:
            raise ValueError(f"No adapter registered for tool: {tool}")
        return adapter

    async def stage_subphase(self, tool: str, action: Dict[str, Any]) -> Dict[str, Any]:
        adapter = self.get_adapter(tool)
        if not adapter.is_available():
            return {"staged": False, "error": f"{tool} is not available"}
        result = await adapter.stage(action)
        result["auto_executed"] = False
        return result

    def route_and_stage(self, description: str, action: Dict[str, Any], preferred_tool: Optional[str] = None) -> Dict[str, Any]:
        """Auto-route to the best tool and stage. Returns result dict."""
        tool = self._router.route(description, preferred_tool)
        # Note: this is a sync wrapper; callers should await stage_subphase
        return {"routed_to": tool, "action": action}
