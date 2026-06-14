"""platforms/abstract/virtual_desktop.py — Abstract base for OS virtual desktop management."""
from __future__ import annotations

import abc
from typing import Any, Dict, List, Optional


class BaseVirtualDesktop(abc.ABC):
    """Abstract interface for creating, switching, and managing OS virtual desktops."""

    @abc.abstractmethod
    def create_desktop(self, name: str) -> str:
        """Create a new virtual desktop and return its ID."""
        raise NotImplementedError

    @abc.abstractmethod
    def switch_to_desktop(self, desktop_id: str) -> None:
        """Switch the current session to the specified desktop."""
        raise NotImplementedError

    @abc.abstractmethod
    def move_window_to_desktop(self, window_handle: int, desktop_id: str) -> None:
        """Move a window to the specified desktop."""
        raise NotImplementedError

    @abc.abstractmethod
    def close_desktop(self, desktop_id: str) -> None:
        """Close a virtual desktop."""
        raise NotImplementedError

    @abc.abstractmethod
    def list_desktops(self) -> List[Dict[str, Any]]:
        """Return a list of desktop dicts with keys: id, name, is_current."""
        raise NotImplementedError

    @abc.abstractmethod
    def current_desktop(self) -> str:
        """Return the ID of the current desktop."""
        raise NotImplementedError

    def get_agent_desktop(self) -> Optional[str]:
        """Return the cached ID of the agent's workflow desktop, if any."""
        return None
