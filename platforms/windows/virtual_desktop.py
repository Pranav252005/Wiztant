"""platforms/windows/virtual_desktop.py — Windows Virtual Desktop implementation.

Uses pyvda (preferred) or direct Win32 COM to manage Windows 10/11 virtual desktops.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from platforms.abstract.virtual_desktop import BaseVirtualDesktop

log = logging.getLogger("platforms.windows.virtual_desktop")


class WindowsVirtualDesktop(BaseVirtualDesktop):
    """Windows virtual desktop manager via pyvda or Win32 COM."""

    def __init__(self) -> None:
        self._agent_desktop_id: Optional[str] = None
        self._pyvda_available = False
        self._try_import_pyvda()

    def _try_import_pyvda(self) -> None:
        """Attempt to import pyvda; mark availability."""
        try:
            import pyvda  # type: ignore[import-untyped]
            self._pyvda = pyvda
            self._pyvda_available = True
            log.info("pyvda loaded successfully")
        except ImportError:
            log.warning("pyvda not installed. Windows virtual desktop features unavailable. "
                        "Install with: pip install pyvda")
            self._pyvda = None

    def create_desktop(self, name: str) -> str:
        """Create a new virtual desktop."""
        if not self._pyvda_available:
            raise RuntimeError("pyvda is required for Windows virtual desktop management")
        try:
            desktop = self._pyvda.VirtualDesktop.create()
            desktop_id = str(desktop.id)
            self._agent_desktop_id = desktop_id
            log.info("Created Windows virtual desktop: %s", desktop_id)
            return desktop_id
        except Exception as e:
            log.error("Failed to create Windows virtual desktop: %s", e)
            raise

    def switch_to_desktop(self, desktop_id: str) -> None:
        """Switch to the specified virtual desktop."""
        if not self._pyvda_available:
            raise RuntimeError("pyvda is required for Windows virtual desktop management")
        try:
            # pyvda desktops can be switched by index or object
            # We store the desktop object for reliability
            if hasattr(self, "_desktop_obj"):
                self._desktop_obj.go()
            else:
                # Fallback: switch by enumerating
                current = self._pyvda.VirtualDesktop.current()
                desktops = self._pyvda.VirtualDesktop.get_all()
                for d in desktops:
                    if str(d.id) == desktop_id:
                        d.go()
                        return
                raise ValueError(f"Desktop {desktop_id} not found")
            log.info("Switched to Windows virtual desktop: %s", desktop_id)
        except Exception as e:
            log.error("Failed to switch Windows virtual desktop: %s", e)
            raise

    def move_window_to_desktop(self, window_handle: int, desktop_id: str) -> None:
        """Move a window to the specified virtual desktop."""
        if not self._pyvda_available:
            raise RuntimeError("pyvda is required for Windows virtual desktop management")
        try:
            app_view = self._pyvda.AppView(window_handle)
            desktops = self._pyvda.VirtualDesktop.get_all()
            target = None
            for d in desktops:
                if str(d.id) == desktop_id:
                    target = d
                    break
            if target is None:
                raise ValueError(f"Desktop {desktop_id} not found")
            app_view.move(target)
            log.info("Moved window %s to desktop %s", window_handle, desktop_id)
        except Exception as e:
            log.error("Failed to move window to desktop: %s", e)
            raise

    def close_desktop(self, desktop_id: str) -> None:
        """Close a virtual desktop."""
        if not self._pyvda_available:
            raise RuntimeError("pyvda is required for Windows virtual desktop management")
        try:
            desktops = self._pyvda.VirtualDesktop.get_all()
            for d in desktops:
                if str(d.id) == desktop_id:
                    d.remove(fallback=self._pyvda.VirtualDesktop.current())
                    log.info("Closed Windows virtual desktop: %s", desktop_id)
                    return
            log.warning("Desktop %s not found for closing", desktop_id)
        except Exception as e:
            log.error("Failed to close Windows virtual desktop: %s", e)
            raise

    def list_desktops(self) -> List[Dict[str, Any]]:
        """List all virtual desktops."""
        if not self._pyvda_available:
            raise RuntimeError("pyvda is required for Windows virtual desktop management")
        try:
            desktops = self._pyvda.VirtualDesktop.get_all()
            current = self._pyvda.VirtualDesktop.current()
            return [
                {
                    "id": str(d.id),
                    "name": getattr(d, "name", f"Desktop {i+1}"),
                    "is_current": d == current,
                }
                for i, d in enumerate(desktops)
            ]
        except Exception as e:
            log.error("Failed to list Windows virtual desktops: %s", e)
            raise

    def current_desktop(self) -> str:
        """Return the current virtual desktop ID."""
        if not self._pyvda_available:
            raise RuntimeError("pyvda is required for Windows virtual desktop management")
        try:
            current = self._pyvda.VirtualDesktop.current()
            return str(current.id)
        except Exception as e:
            log.error("Failed to get current Windows virtual desktop: %s", e)
            raise

    def get_agent_desktop(self) -> Optional[str]:
        return self._agent_desktop_id
