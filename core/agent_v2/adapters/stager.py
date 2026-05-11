"""Stager: routes subphases to the correct adapter and enforces 'type but don't press Enter'."""

from __future__ import annotations

from typing import Any, Dict

from core.agent_v2.adapters.base import ToolAdapter
from core.agent_v2.adapters.cursor_adapter import CursorAdapter
from core.agent_v2.adapters.warp_adapter import WarpAdapter


class Stager:
    """Orchestrates staging across multiple tool adapters."""

    def __init__(self) -> None:
        self._adapters: Dict[str, ToolAdapter] = {
            "cursor": CursorAdapter(),
            "warp": WarpAdapter(),
        }

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
