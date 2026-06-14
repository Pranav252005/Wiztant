"""platforms/linux/virtual_desktop.py — Linux virtual desktop implementation.

Uses xdotool and wmctrl with EWMH (Extended Window Manager Hints) to manage
virtual desktops on X11. Works on most WMs (i3, bspwm, Openbox, some GNOME/XFCE).
"""
from __future__ import annotations

import logging
import subprocess
from typing import Any, Dict, List, Optional

from platforms.abstract.virtual_desktop import BaseVirtualDesktop

log = logging.getLogger("platforms.linux.virtual_desktop")


class VirtualDesktopUnsupported(RuntimeError):
    """Raised when the Linux WM does not support virtual desktop operations."""
    pass


class LinuxVirtualDesktop(BaseVirtualDesktop):
    """Linux virtual desktop manager via xdotool / wmctrl."""

    def __init__(self) -> None:
        self._agent_desktop_id: Optional[str] = None
        self._has_xdotool = self._check_tool("xdotool")
        self._has_wmctrl = self._check_tool("wmctrl")

    def _check_tool(self, name: str) -> bool:
        """Check if a command-line tool is available."""
        try:
            subprocess.run([name, "--version"], capture_output=True, check=True)
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            return False

    def _run(self, cmd: List[str]) -> str:
        """Run a command and return stdout, raising on errors."""
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)} — {result.stderr.strip()}")
        return result.stdout.strip()

    def create_desktop(self, name: str) -> str:
        """Create a new virtual desktop by incrementing the count."""
        if not self._has_xdotool:
            raise VirtualDesktopUnsupported("xdotool is required for Linux virtual desktop management")
        try:
            current_count = int(self._run(["xdotool", "get_num_desktops"]))
            new_count = current_count + 1
            self._run(["xdotool", "set_num_desktops", str(new_count)])
            # Desktop IDs are 0-indexed
            new_id = str(current_count)
            self._agent_desktop_id = new_id
            log.info("Created Linux virtual desktop: %s (total=%s)", new_id, new_count)
            return new_id
        except Exception as e:
            log.error("Failed to create Linux virtual desktop: %s", e)
            raise

    def switch_to_desktop(self, desktop_id: str) -> None:
        """Switch to the specified virtual desktop."""
        if not self._has_xdotool:
            raise VirtualDesktopUnsupported("xdotool is required for Linux virtual desktop management")
        try:
            self._run(["xdotool", "set_desktop", desktop_id])
            log.info("Switched to Linux virtual desktop: %s", desktop_id)
        except Exception as e:
            log.error("Failed to switch Linux virtual desktop: %s", e)
            raise

    def move_window_to_desktop(self, window_handle: int, desktop_id: str) -> None:
        """Move a window to the specified virtual desktop."""
        if self._has_wmctrl:
            try:
                self._run(["wmctrl", "-i", "-r", hex(window_handle), "-t", desktop_id])
                log.info("Moved window %s to desktop %s", window_handle, desktop_id)
                return
            except Exception as e:
                log.warning("wmctrl move failed, trying xdotool fallback: %s", e)
        if self._has_xdotool:
            try:
                self._run(["xdotool", "set_desktop_for_window", str(window_handle), desktop_id])
                log.info("Moved window %s to desktop %s", window_handle, desktop_id)
                return
            except Exception as e:
                log.error("Failed to move window to desktop: %s", e)
                raise
        raise VirtualDesktopUnsupported("wmctrl or xdotool required for window desktop movement")

    def close_desktop(self, desktop_id: str) -> None:
        """Close a virtual desktop by decrementing the count."""
        if not self._has_xdotool:
            raise VirtualDesktopUnsupported("xdotool is required for Linux virtual desktop management")
        try:
            # Move any windows on this desktop to desktop 0 first
            current = self._run(["xdotool", "get_desktop"])
            if current == desktop_id:
                self._run(["xdotool", "set_desktop", "0"])

            # Decrement desktop count
            current_count = int(self._run(["xdotool", "get_num_desktops"]))
            if current_count > 1:
                self._run(["xdotool", "set_num_desktops", str(current_count - 1)])
            log.info("Closed Linux virtual desktop: %s", desktop_id)
        except Exception as e:
            log.error("Failed to close Linux virtual desktop: %s", e)
            raise

    def list_desktops(self) -> List[Dict[str, Any]]:
        """List all virtual desktops."""
        if not self._has_xdotool:
            raise VirtualDesktopUnsupported("xdotool is required for Linux virtual desktop management")
        try:
            count = int(self._run(["xdotool", "get_num_desktops"]))
            current = int(self._run(["xdotool", "get_desktop"]))
            return [
                {
                    "id": str(i),
                    "name": f"Desktop {i + 1}",
                    "is_current": i == current,
                }
                for i in range(count)
            ]
        except Exception as e:
            log.error("Failed to list Linux virtual desktops: %s", e)
            raise

    def current_desktop(self) -> str:
        """Return the current virtual desktop ID."""
        if not self._has_xdotool:
            raise VirtualDesktopUnsupported("xdotool is required for Linux virtual desktop management")
        try:
            return self._run(["xdotool", "get_desktop"])
        except Exception as e:
            log.error("Failed to get current Linux virtual desktop: %s", e)
            raise

    def get_agent_desktop(self) -> Optional[str]:
        return self._agent_desktop_id
