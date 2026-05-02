"""platforms/windows/window_mgmt.py — Windows window management implementing BaseWindowMgmt."""
from __future__ import annotations

import ctypes
import time
from typing import Any, List, Tuple

from platforms.abstract import BaseWindowMgmt


class WindowsWindowMgmt(BaseWindowMgmt):
    """Windows window management via win32gui and win32con."""

    def get_active_window(self) -> dict:
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            return {"id": hwnd, "name": title, "backend": "win32"}
        except Exception as e:
            return {"id": None, "name": "", "backend": "win32", "error": str(e)}

    def get_window_class_name(self) -> str:
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            return win32gui.GetClassName(hwnd)
        except Exception:
            return "Unknown"

    def list_windows(self) -> List[Tuple[str, Any]]:
        try:
            import win32gui
            results: List[Tuple[str, int]] = []
            def _cb(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    t = win32gui.GetWindowText(hwnd) or ""
                    if t.strip():
                        results.append((t, hwnd))
            win32gui.EnumWindows(_cb, None)
            return results
        except Exception:
            return []

    def focus_window(self, window_id: Any) -> bool:
        try:
            import win32gui, win32con
            hwnd = int(window_id)
            placement = win32gui.GetWindowPlacement(hwnd)
            if placement[1] == win32con.SW_SHOWMINIMIZED:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.3)
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.4)
            return True
        except Exception:
            return False

    def get_window_bounds(self, window_id: Any) -> Tuple[int, int, int, int]:
        try:
            import win32gui
            hwnd = int(window_id)
            rect = win32gui.GetWindowRect(hwnd)
            return rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1]
        except Exception:
            return 0, 0, 0, 0

    def create_overlay(self, width: int, height: int) -> Any:
        # Windows overlays are handled by Electron or tkinter directly
        return None

    def minimize_window(self) -> None:
        try:
            import win32gui, win32con
            hwnd = win32gui.GetForegroundWindow()
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        except Exception as e:
            print(f"[WindowMgmt/Windows] minimize failed: {e}")

    def open_file(self, path: str) -> None:
        import os
        os.startfile(path)
