"""Abstract base for tool adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple


class ToolAdapter(ABC):
    """Adapter that stages actions in an external tool without auto-executing."""

    name: str = "abstract"

    @abstractmethod
    async def stage(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Stage an action. Return a result dict with 'staged': bool and 'details'."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the target tool is installed/running."""

    def _get_runtime(self):
        """Lazy-load the platform agent runtime."""
        from platforms.factory import get_agent_runtime
        return get_agent_runtime()
