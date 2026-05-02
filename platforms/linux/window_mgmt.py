"""platforms/linux/window_mgmt.py — Linux window management implementing BaseWindowMgmt."""
from __future__ import annotations

import subprocess
from typing import Any, List, Tuple

from platforms.abstract import BaseWindowMgmt


class LinuxWindowMgmt(BaseWindowMgmt):
    """Linux window management via xdotool (X11) and gdbus (Wayland)."""

    def get_active_window(self) -> dict:
        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().splitlines()
                name = lines[0] if lines else ""
                return {"id": None, "name": name, "backend": "x11"}
        except FileNotFoundError:
            pass

        try:
            result = subprocess.run(
                ["gdbus", "call", "--session",
                 "--dest", "org.gnome.Shell",
                 "--object-path", "/org/gnome/Shell",
                 "--method", "org.freedesktop.DBus.Properties.Get",
                 "org.gnome.Shell", "FocusWindow"],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0:
                return {"id": None, "name": result.stdout.strip(), "backend": "wayland"}
        except FileNotFoundError:
            pass

        return {"id": None, "name": "", "backend": "unknown"}

    def get_window_class_name(self) -> str:
        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True, text=True, timeout=2,
            )
            name = result.stdout.lower()
            if "chrome" in name or "chromium" in name:
                return "Chrome"
            if "firefox" in name:
                return "Firefox"
            if "code" in name:
                return "VSCode"
            if "outlook" in name or "thunderbird" in name:
                return "Email"
            if "slack" in name:
                return "Slack"
            return "Unknown"
        except Exception:
            return "Unknown"

    def list_windows(self) -> List[Tuple[str, Any]]:
        try:
            result = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                out: List[Tuple[str, str]] = []
                for line in result.stdout.strip().split("\n"):
                    parts = line.split(None, 3)
                    if len(parts) >= 4:
                        out.append((parts[3], parts[0]))
                return out
        except Exception:
            pass
        return []

    def focus_window(self, window_id: Any) -> bool:
        try:
            subprocess.run(["wmctrl", "-ia", str(window_id)], capture_output=True, timeout=2)
            return True
        except Exception:
            pass
        try:
            subprocess.run(["xdotool", "windowactivate", str(window_id)], capture_output=True, timeout=2)
            return True
        except Exception:
            return False

    def get_window_bounds(self, window_id: Any) -> Tuple[int, int, int, int]:
        try:
            result = subprocess.run(
                ["xdotool", "getwindowgeometry", str(window_id)],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0:
                # Parse xdotool output
                x, y, w, h = 0, 0, 0, 0
                for line in result.stdout.strip().split("\n"):
                    if "Position:" in line:
                        # e.g., "Position: 100,200 (screen: 0)"
                        pos = line.split(":", 1)[1].split("(")[0].strip()
                        x_str, y_str = pos.split(",")
                        x, y = int(x_str.strip()), int(y_str.strip())
                    elif "Geometry:" in line:
                        geo = line.split(":", 1)[1].strip()
                        w_str, h_str = geo.split("x")
                        w, h = int(w_str.strip()), int(h_str.strip())
                return x, y, w, h
        except Exception:
            pass
        return 0, 0, 0, 0

    def create_overlay(self, width: int, height: int) -> Any:
        # Linux overlays are handled by Electron or tkinter directly
        return None

    def minimize_window(self) -> None:
        try:
            subprocess.run(
                ["xdotool", "getactivewindow", "windowminimize"],
                timeout=2, check=True,
            )
        except Exception as e:
            print(f"[WindowMgmt/Linux] minimize failed: {e}")

    def open_file(self, path: str) -> None:
        subprocess.Popen(["xdg-open", path])
