"""platforms/windows/system_access.py — Windows system access implementing BaseSystemAccess."""
from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import sys
import time
from typing import Any, List, Optional, Tuple

from PIL import Image
from mss import mss

from platforms.abstract import BaseSystemAccess

log = logging.getLogger("platforms.windows.system_access")

_WINDOWS_BROWSER_PATHS: dict[str, Tuple[str, ...]] = {
    "chrome": (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ),
    "arc": tuple(p for p in (
        os.path.join(os.getenv("LOCALAPPDATA", ""), "Programs", "Arc", "Arc.exe"),
        r"C:\Program Files\Arc\Arc.exe",
    ) if p),
    "firefox": (
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    ),
    "msedge": (
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ),
}

_WINDOWS_BROWSER_EXES = {
    "chrome": "chrome.exe", "arc": "Arc.exe",
    "firefox": "firefox.exe", "msedge": "msedge.exe",
    "brave": "brave.exe", "opera": "opera.exe", "vivaldi": "vivaldi.exe",
}


class WindowsSystemAccess(BaseSystemAccess):
    """Windows system access via pyautogui, win32 APIs, and subprocess."""

    def __init__(self):
        self._pyautogui = None
        self._pyautogui_ok = False
        try:
            import pyautogui
            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0.05
            self._pyautogui = pyautogui
            self._pyautogui_ok = True
        except Exception as e:
            log.warning("pyautogui not available: %s", e)

    # ── Screenshots ───────────────────────────────────────────────────────────

    def take_screenshot(self) -> Image.Image:
        with mss() as sct:
            monitor = sct.monitors[0]
            raw = sct.grab(monitor)
            return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

    def list_monitors(self) -> List[dict]:
        with mss() as sct:
            return [dict(m) for m in sct.monitors[1:]]

    def screen_size(self) -> Tuple[int, int]:
        with mss() as sct:
            mon = sct.monitors[0]
            return int(mon["width"]), int(mon["height"])

    # ── Clipboard ─────────────────────────────────────────────────────────────

    def get_clipboard(self) -> str:
        try:
            import pyperclip
            return pyperclip.paste() or ""
        except Exception:
            return ""

    def set_clipboard(self, text: str) -> None:
        try:
            import pyperclip
            pyperclip.copy(text)
        except Exception:
            pass

    # ── Cursor ──────────────────────────────────────────────────────────────────

    def cursor_position(self) -> Tuple[int, int]:
        try:
            import pyautogui
            return pyautogui.position()
        except Exception:
            return (0, 0)

    # ── Input (mouse / keyboard) ──────────────────────────────────────────────

    def click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> Tuple[bool, str]:
        if self._pyautogui_ok:
            try:
                self._pyautogui.click(x, y, button=button, clicks=clicks)
                return True, f"clicked at ({x}, {y})"
            except Exception as e:
                return False, f"click failed: {e}"
        return False, "no input backend available"

    def move(self, x: int, y: int) -> Tuple[bool, str]:
        if self._pyautogui_ok:
            try:
                self._pyautogui.moveTo(x, y, duration=0.0)
                return True, f"moved to ({x}, {y})"
            except Exception as e:
                return False, f"move failed: {e}"
        return False, "no input backend available"

    def scroll(self, x: int, y: int, amount: int) -> Tuple[bool, str]:
        if self._pyautogui_ok:
            try:
                self._pyautogui.scroll(amount, x=x, y=y)
                return True, f"scrolled at ({x}, {y})"
            except Exception as e:
                return False, f"scroll failed: {e}"
        return False, "no input backend available"

    def type_text(self, text: str, interval: float = 0.01) -> Tuple[bool, str]:
        if self._pyautogui_ok:
            try:
                self._pyautogui.typewrite(text, interval=interval)
                return True, f"typed '{text[:50]}{'...' if len(text) > 50 else ''}'"
            except Exception as e:
                return False, f"type failed: {e}"
        return False, "no input backend available"

    def press_key(self, key: str) -> Tuple[bool, str]:
        if self._pyautogui_ok:
            try:
                self._pyautogui.press(key)
                return True, f"pressed {key}"
            except Exception as e:
                return False, f"press failed: {e}"
        return False, "no input backend available"

    def hotkey(self, *keys: str) -> Tuple[bool, str]:
        blocked = {"alt+f4", "ctrl+alt+delete", "super+q", "ctrl+alt+t"}
        combo_str = "+".join(keys).lower()
        if combo_str in blocked:
            log.warning("Blocked unsafe key combo: %s", combo_str)
            return False, f"blocked unsafe combo: {combo_str}"

        if self._pyautogui_ok:
            try:
                self._pyautogui.hotkey(*keys)
                return True, f"hotkey {'+'.join(keys)}"
            except Exception as e:
                return False, f"hotkey failed: {e}"
        return False, "no input backend available"

    # ── App / Window ──────────────────────────────────────────────────────────

    def _windows_default_browser(self) -> str:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice") as key:
                prog_id, _ = winreg.QueryValueEx(key, "ProgId")
            pl = prog_id.lower()
            if "arc" in pl: return "arc"
            if "chrome" in pl: return "chrome"
            if "firefox" in pl: return "firefox"
            if "msedge" in pl or "edge" in pl: return "msedge"
            if "brave" in pl: return "brave"
            if "opera" in pl: return "opera"
            if "vivaldi" in pl: return "vivaldi"
        except Exception:
            pass
        return "start"

    def _windows_resolve_browser(self, name: str) -> Optional[str]:
        from core.agent_engine import KNOWN_APPS
        req = (name or "").strip().lower()
        if req in {"browser", "web browser", "default browser"}:
            req = self._windows_default_browser()
        canonical = KNOWN_APPS.get(req, req)
        exe_name = _WINDOWS_BROWSER_EXES.get(canonical)
        if not exe_name:
            return None
        for path in _WINDOWS_BROWSER_PATHS.get(canonical, ()):
            if path and os.path.exists(path):
                return path
        try:
            import winreg
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for subpath in (
                    rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}",
                    rf"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}",
                ):
                    try:
                        with winreg.OpenKey(hive, subpath) as key:
                            raw, _ = winreg.QueryValueEx(key, "")
                        if raw and os.path.exists(str(raw)):
                            return str(raw)
                    except Exception:
                        continue
        except Exception:
            pass
        return None

    def launch_app(self, app_name: str) -> str:
        if not app_name:
            return "no app specified"
        try:
            subprocess.Popen(app_name, shell=True)
            time.sleep(1.5)
            return f"launched {app_name}"
        except Exception as e:
            log.error("launch_app(%r) failed: %s", app_name, e)
            return f"failed to launch {app_name}: {e}"

    def _get_chrome_profiles_windows(self, browser_name: str) -> List[str]:
        """Return available Chrome/Edge profile directory names on Windows."""
        local_appdata = os.getenv("LOCALAPPDATA", "")
        browser_to_dir = {
            "chrome": os.path.join(local_appdata, "Google", "Chrome", "User Data"),
            "chromium": os.path.join(local_appdata, "Chromium", "User Data"),
            "msedge": os.path.join(local_appdata, "Microsoft", "Edge", "User Data"),
        }
        profile_dir = browser_to_dir.get(browser_name.lower())
        if not profile_dir or not os.path.isdir(profile_dir):
            return []
        profiles = []
        try:
            for entry in os.listdir(profile_dir):
                entry_path = os.path.join(profile_dir, entry)
                if os.path.isdir(entry_path) and entry.startswith("Profile"):
                    profiles.append(entry)
                elif entry == "Default" and os.path.isdir(entry_path):
                    profiles.insert(0, entry)
        except Exception:
            pass
        return profiles

    def launch_browser(self, name: str, url: Optional[str] = None, profile: Optional[str] = None) -> str:
        path = self._windows_resolve_browser(name)
        if not path:
            return f"failed to launch {name}: browser not found"
        cmd = [path]

        # Chrome/Chromium/Edge: add profile flag to skip profile picker
        browser_lower = name.strip().lower()
        is_chromium_like = browser_lower in ("chrome", "chromium", "msedge", "edge", "browser")
        if is_chromium_like:
            profiles = self._get_chrome_profiles_windows(browser_lower)
            chosen_profile = profile or "Default"
            if chosen_profile == "Default" and "Default" not in profiles and profiles:
                chosen_profile = profiles[0]
            cmd.append(f"--profile-directory={chosen_profile}")
            cmd.extend(["--no-first-run", "--no-default-browser-check"])

        if url:
            cmd.append(url)
        try:
            subprocess.Popen(cmd)
            time.sleep(2.0)
            profile_msg = f" (profile: {chosen_profile})" if is_chromium_like and profile else ""
            return f"launched {name}{profile_msg}"
        except Exception as e:
            return f"failed to launch {name}: {e}"

    def ensure_app_open(self, app_name: str, url: Optional[str] = None, profile: Optional[str] = None) -> str:
        name_lower = app_name.lower().strip()
        try:
            import win32gui, win32con
        except Exception:
            return self.launch_app(app_name)
        fw = win32gui.GetForegroundWindow()
        if name_lower in win32gui.GetWindowText(fw).lower():
            return f"{app_name} already focused"
        matches: list[int] = []
        def _find(hwnd, _):
            if name_lower in win32gui.GetWindowText(hwnd).lower():
                matches.append(hwnd)
        win32gui.EnumWindows(_find, None)
        if matches:
            win32gui.ShowWindow(matches[0], win32con.SW_RESTORE)
            try:
                ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0x12, 0, 0x0002, 0)
            except Exception:
                pass
            win32gui.SetForegroundWindow(matches[0])
            time.sleep(1.0)
            return f"raised {app_name}"
        return self.launch_app(app_name)

    def raise_window(self, window_id: Any) -> bool:
        try:
            import win32gui, win32con
            hwnd = int(window_id)
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            try:
                ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0x12, 0, 0x0002, 0)
            except Exception:
                pass
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.25)
            return True
        except Exception as e:
            log.warning("raise_window failed: %s", e)
            return False

    def get_foreground_app(self) -> str:
        try:
            import win32gui
            return win32gui.GetWindowText(win32gui.GetForegroundWindow()) or ""
        except Exception:
            return ""

    def open_file(self, path: str) -> None:
        os.startfile(path)

    def open_browser(self, url: str, profile: str | None = None) -> bool:
        import webbrowser
        try:
            webbrowser.open(url, new=2)
            return True
        except Exception:
            return False

    # ── Misc ────────────────────────────────────────────────────────────────────

    def execute(self, command: str | List[str]) -> Tuple[bool, str]:
        try:
            if isinstance(command, str):
                result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            else:
                result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            return result.returncode == 0, result.stdout or result.stderr
        except Exception as e:
            return False, str(e)
