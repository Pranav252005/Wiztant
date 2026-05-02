"""core/window_manager.py — App/window detection, launching, and switching.

Delegates all platform-specific operations to the Platform Abstraction Layer.
"""
from __future__ import annotations

import logging
import os
import subprocess
import time
from typing import Optional

from platforms.factory import get_window_mgmt, get_system_access

logger = logging.getLogger(__name__)


class WindowManager:
    """Detect, launch, and switch application windows via PAL."""

    def __init__(self):
        self._wm = get_window_mgmt()
        self._sys = get_system_access()
        self._current_id: Optional[int] = None

    def _get_all_windows(self) -> dict[str, Any]:
        """Return {title: window_id} for all visible, non-empty titled windows."""
        try:
            windows = self._wm.list_windows()
            return {title: wid for title, wid in windows if title.strip()}
        except Exception as e:
            logger.error("[WindowManager] list_windows failed: %s", e)
            return {}

    def _find_id_for_app(self, app_name: str) -> Optional[Any]:
        from core.app_detector import get_window_title_hints
        app_name_lower = app_name.lower().strip()
        hints = [h.lower() for h in get_window_title_hints(app_name_lower)]
        if not hints:
            hints = [app_name_lower]

        windows = self._get_all_windows()
        for title, wid in windows.items():
            title_lower = title.lower()
            if any(hint in title_lower for hint in hints):
                logger.info("[WindowManager] Found '%s' -> '%s' (id=%s)", app_name, title, wid)
                return wid
        return None

    def _bring_to_front(self, wid: Any) -> bool:
        """Restore + foreground a window."""
        try:
            ok = self._wm.focus_window(wid)
            if ok:
                self._current_id = wid
                logger.info("[WindowManager] Brought id=%s to foreground", wid)
            return ok
        except Exception as e:
            logger.error("[WindowManager] _bring_to_front failed: %s", e)
            return False

    # ── Public API ────────────────────────────────────────────────────────────

    def is_app_open(self, app_name: str) -> bool:
        return self._find_id_for_app(app_name) is not None

    def switch_to_app(self, app_name: str) -> bool:
        logger.info("[WindowManager] Switching to '%s'...", app_name)
        wid = self._find_id_for_app(app_name)
        if not wid:
            logger.warning("[WindowManager] '%s' not found in open windows", app_name)
            return False
        return self._bring_to_front(wid)

    def open_app(self, app_name: str) -> bool:
        from core.app_detector import get_launch_path
        app_name_lower = app_name.lower().strip()
        logger.info("[WindowManager] open_app('%s')", app_name)

        if self.is_app_open(app_name_lower):
            logger.info("[WindowManager] '%s' already running — switching", app_name)
            return self.switch_to_app(app_name_lower)

        path = get_launch_path(app_name_lower)
        if not path:
            logger.error("[WindowManager] No launch path in app_config.json for '%s'", app_name)
            return False

        logger.info("[WindowManager] Launching '%s' -> %s", app_name, path)
        try:
            if path.startswith("ms-"):
                subprocess.Popen(["start", path], shell=True)
            elif path.endswith(".exe") and not os.path.isabs(path):
                subprocess.Popen(path, shell=True)
            else:
                subprocess.Popen([path])
        except Exception as e:
            logger.error("[WindowManager] Launch failed for '%s': %s", app_name, e)
            return False

        for _ in range(16):
            time.sleep(0.5)
            if self.is_app_open(app_name_lower):
                logger.info("[WindowManager] '%s' window appeared — switching", app_name)
                return self.switch_to_app(app_name_lower)

        logger.error("[WindowManager] '%s' window did not appear within 8s", app_name)
        return False

    def get_foreground_app_title(self) -> str:
        try:
            info = self._wm.get_active_window()
            return info.get("name", "").strip()
        except Exception:
            return "Unknown"

    def detect_app_in_instruction(self, instruction: str) -> Optional[str]:
        from core.app_detector import detect_app_from_request
        return detect_app_from_request(instruction)


# ── Singleton ───────────────────────────────────────────────────────────────

_window_manager: Optional[WindowManager] = None


def get_window_manager() -> WindowManager:
    global _window_manager
    if _window_manager is None:
        _window_manager = WindowManager()
    return _window_manager
