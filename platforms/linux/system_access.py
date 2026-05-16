"""platforms/linux/system_access.py — Linux system access implementing BaseSystemAccess."""
from __future__ import annotations

import io
import logging
import os
import shutil
import subprocess
import sys
import time
from typing import Any, List, Optional, Tuple

from PIL import Image
from mss import mss

from platforms.abstract import BaseSystemAccess

log = logging.getLogger("platforms.linux.system_access")

_LINUX_APP_COMMANDS: dict[str, str] = {
    "chrome": "google-chrome",
    "google chrome": "google-chrome",
    "chromium": "chromium-browser",
    "firefox": "firefox",
    "edge": "microsoft-edge",
    "browser": "google-chrome",
    "terminal": "gnome-terminal",
    "gnome terminal": "gnome-terminal",
    "konsole": "konsole",
    "xfce4-terminal": "xfce4-terminal",
    "code": "code",
    "vscode": "code",
    "vs code": "code",
    "visual studio code": "code",
    "files": "nautilus",
    "file manager": "nautilus",
    "explorer": "nautilus",
    "nautilus": "nautilus",
    "dolphin": "dolphin",
    "thunar": "thunar",
    "pcmanfm": "pcmanfm",
    "text editor": "gedit",
    "notepad": "gedit",
    "gedit": "gedit",
    "mousepad": "mousepad",
    "leafpad": "leafpad",
    "calculator": "gnome-calculator",
    "kcalc": "kcalc",
    "settings": "gnome-control-center",
    "system settings": "gnome-control-center",
}


class LinuxSystemAccess(BaseSystemAccess):
    """Linux system access via xdotool, wmctrl, and subprocess."""

    def __init__(self):
        self._pynput_ok = False
        self._mouse = None
        self._keyboard = None
        try:
            from pynput.mouse import Controller as MouseController, Button
            from pynput.keyboard import Controller as KeyboardController, Key
            self._mouse = MouseController()
            self._keyboard = KeyboardController()
            self._pynput_ok = True
        except Exception:
            pass

    # ── Screenshots ───────────────────────────────────────────────────────────

    def take_screenshot(self) -> Image.Image:
        """Capture full-screen screenshot with multiple fallbacks.

        Primary: mss (fastest, X11 via ctypes).
        Fallbacks: scrot, gnome-screenshot, spectacle, ImageMagick import,
                   ffmpeg x11grab, xwd.
        Raises RuntimeError only when every mechanism fails.
        """
        # 1. mss (primary)
        try:
            with mss() as sct:
                monitor = sct.monitors[0]
                raw = sct.grab(monitor)
                return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        except Exception as e:
            log.debug("mss screenshot failed: %s", e)

        # 2. scrot
        if shutil.which("scrot"):
            try:
                result = subprocess.run(["scrot", "-"], capture_output=True, timeout=5)
                if result.returncode == 0 and result.stdout:
                    return Image.open(io.BytesIO(result.stdout)).convert("RGB")
            except Exception as e:
                log.debug("scrot screenshot failed: %s", e)

        # 3. gnome-screenshot
        if shutil.which("gnome-screenshot"):
            try:
                result = subprocess.run(["gnome-screenshot", "-f", "/dev/stdout"], capture_output=True, timeout=5)
                if result.returncode == 0 and result.stdout:
                    return Image.open(io.BytesIO(result.stdout)).convert("RGB")
            except Exception as e:
                log.debug("gnome-screenshot failed: %s", e)

        # 4. spectacle (KDE)
        if shutil.which("spectacle"):
            try:
                result = subprocess.run(["spectacle", "-b", "-o", "-"], capture_output=True, timeout=5)
                if result.returncode == 0 and result.stdout:
                    return Image.open(io.BytesIO(result.stdout)).convert("RGB")
            except Exception as e:
                log.debug("spectacle failed: %s", e)

        # 5. ImageMagick import
        if shutil.which("import"):
            try:
                result = subprocess.run(["import", "-window", "root", "png:-"], capture_output=True, timeout=5)
                if result.returncode == 0 and result.stdout:
                    return Image.open(io.BytesIO(result.stdout)).convert("RGB")
            except Exception as e:
                log.debug("ImageMagick import failed: %s", e)

        # 6. ffmpeg x11grab
        display = os.getenv("DISPLAY", ":0")
        if shutil.which("ffmpeg"):
            try:
                result = subprocess.run(
                    ["ffmpeg", "-f", "x11grab", "-i", f"{display}", "-vframes", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                    capture_output=True, timeout=5,
                )
                if result.returncode == 0 and result.stdout:
                    return Image.open(io.BytesIO(result.stdout)).convert("RGB")
            except Exception as e:
                log.debug("ffmpeg x11grab failed: %s", e)

        # 7. xwd + convert via ImageMagick
        if shutil.which("xwd") and shutil.which("convert"):
            try:
                xwd_proc = subprocess.run(["xwd", "-root", "-silent"], capture_output=True, timeout=5)
                if xwd_proc.returncode == 0 and xwd_proc.stdout:
                    convert_proc = subprocess.run(["convert", "xwd:-", "png:-"], input=xwd_proc.stdout, capture_output=True, timeout=5)
                    if convert_proc.returncode == 0 and convert_proc.stdout:
                        return Image.open(io.BytesIO(convert_proc.stdout)).convert("RGB")
            except Exception as e:
                log.debug("xwd+convert failed: %s", e)

        raise RuntimeError(
            "Screenshot failed. All backends (mss, scrot, gnome-screenshot, spectacle, "
            "ImageMagick, ffmpeg, xwd) failed. Ensure you have an active desktop session."
        )

    def list_monitors(self) -> List[dict]:
        try:
            with mss() as sct:
                return [dict(m) for m in sct.monitors[1:]]
        except Exception:
            return []

    def screen_size(self) -> Tuple[int, int]:
        try:
            with mss() as sct:
                mon = sct.monitors[0]
                return int(mon["width"]), int(mon["height"])
        except Exception:
            pass
        # Fallback: xrandr
        if shutil.which("xrandr"):
            try:
                result = subprocess.run(["xrandr"], capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        m = __import__("re").search(r"(\d+)x(\d+)\+\d+\+\d+", line)
                        if m:
                            return int(m.group(1)), int(m.group(2))
            except Exception:
                pass
        # Fallback: xdpyinfo
        if shutil.which("xdpyinfo"):
            try:
                result = subprocess.run(["xdpyinfo"], capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        if "dimensions:" in line:
                            parts = line.split()
                            for p in parts:
                                if "x" in p:
                                    w, h = p.split("x")[:2]
                                    return int(w), int(h)
            except Exception:
                pass
        return (1920, 1080)

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
        if self._pynput_ok:
            try:
                return self._mouse.position
            except Exception:
                pass
        try:
            result = subprocess.run(
                ["xdotool", "getmouselocation", "--shell"],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line.startswith("X="):
                        x = int(line.split("=", 1)[1])
                    elif line.startswith("Y="):
                        y = int(line.split("=", 1)[1])
                return x, y
        except Exception:
            pass
        return (0, 0)

    # ── Input (mouse / keyboard) ──────────────────────────────────────────────

    def click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> Tuple[bool, str]:
        if self._pynput_ok:
            try:
                from pynput.mouse import Button
                btn = Button.right if button == "right" else Button.left
                self._mouse.position = (x, y)
                time.sleep(0.05)
                self._mouse.click(btn, clicks)
                time.sleep(0.12)
                return True, f"clicked at ({x}, {y})"
            except Exception as e:
                return False, f"click failed: {e}"
        # Fallback: xdotool
        try:
            b = "3" if button == "right" else "1"
            subprocess.run(["xdotool", "mousemove", str(x), str(y), "click", "--repeat", str(clicks), b], timeout=5, check=True)
            return True, f"clicked at ({x}, {y})"
        except Exception as e:
            return False, f"click failed: {e}"

    def move(self, x: int, y: int) -> Tuple[bool, str]:
        if self._pynput_ok:
            try:
                self._mouse.position = (x, y)
                return True, f"moved to ({x}, {y})"
            except Exception as e:
                return False, f"move failed: {e}"
        try:
            subprocess.run(["xdotool", "mousemove", str(x), str(y)], timeout=5, check=True)
            return True, f"moved to ({x}, {y})"
        except Exception as e:
            return False, f"move failed: {e}"

    def scroll(self, x: int, y: int, amount: int) -> Tuple[bool, str]:
        if self._pynput_ok:
            try:
                self._mouse.position = (x, y)
                time.sleep(0.05)
                self._mouse.scroll(0, amount)
                time.sleep(0.12)
                return True, f"scrolled at ({x}, {y})"
            except Exception as e:
                return False, f"scroll failed: {e}"
        try:
            subprocess.run(["xdotool", "mousemove", str(x), str(y), "scroll", str(amount)], timeout=5, check=True)
            return True, f"scrolled at ({x}, {y})"
        except Exception as e:
            return False, f"scroll failed: {e}"

    def type_text(self, text: str, interval: float = 0.01) -> Tuple[bool, str]:
        # Detect display server: Wayland or X11
        session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
        is_wayland = session_type == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY"))

        # On X11, pynput may work; on Wayland it often silently fails.
        if self._pynput_ok and not is_wayland:
            try:
                self._keyboard.type(text)
                return True, f"typed '{text[:50]}{'...' if len(text) > 50 else ''}'"
            except Exception as e:
                return False, f"type failed: {e}"

        # Fallbacks: xdotool (X11), wtype (Wayland), ydotool (Wayland)
        if not is_wayland and shutil.which("xdotool"):
            try:
                subprocess.run(["xdotool", "type", "--delay", "1", text], timeout=5, check=True)
                return True, f"typed (xdotool) '{text[:50]}{'...' if len(text) > 50 else ''}'"
            except Exception as e:
                return False, f"xdotool type failed: {e}"

        if shutil.which("wtype"):
            try:
                subprocess.run(["wtype", text], timeout=5, check=True)
                return True, f"typed (wtype) '{text[:50]}{'...' if len(text) > 50 else ''}'"
            except Exception as e:
                return False, f"wtype failed: {e}"

        if shutil.which("ydotool"):
            try:
                subprocess.run(["ydotool", "type", "--delay", "1", text], timeout=5, check=True)
                return True, f"typed (ydotool) '{text[:50]}{'...' if len(text) > 50 else ''}'"
            except Exception as e:
                return False, f"ydotool type failed: {e}"

        # Last resort: try pynput even on Wayland (may fail silently)
        if self._pynput_ok:
            try:
                self._keyboard.type(text)
                return True, f"typed (pynput fallback) '{text[:50]}{'...' if len(text) > 50 else ''}'"
            except Exception as e:
                return False, f"pynput type failed: {e}"

        return False, "no input backend available"

    def press_key(self, key: str) -> Tuple[bool, str]:
        session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
        is_wayland = session_type == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY"))

        if self._pynput_ok and not is_wayland:
            try:
                kobj = self._key_name_to_pynput(key)
                pressed = []
                try:
                    if isinstance(kobj, str):
                        self._keyboard.press(kobj)
                        pressed.append(kobj)
                    else:
                        self._keyboard.press(kobj)
                        pressed.append(kobj)
                    time.sleep(0.12)
                    return True, f"pressed {key}"
                finally:
                    for k in reversed(pressed):
                        try:
                            self._keyboard.release(k)
                        except Exception:
                            pass
            except Exception as e:
                return False, f"press failed: {e}"
        if shutil.which("xdotool"):
            try:
                subprocess.run(["xdotool", "key", key], timeout=5, check=True)
                return True, f"pressed {key}"
            except Exception as e:
                return False, f"press failed: {e}"
        # Last resort: pynput even on Wayland
        if self._pynput_ok:
            try:
                kobj = self._key_name_to_pynput(key)
                pressed = []
                try:
                    if isinstance(kobj, str):
                        self._keyboard.press(kobj)
                        pressed.append(kobj)
                    else:
                        self._keyboard.press(kobj)
                        pressed.append(kobj)
                    time.sleep(0.12)
                    return True, f"pressed {key} (pynput fallback)"
                finally:
                    for k in reversed(pressed):
                        try:
                            self._keyboard.release(k)
                        except Exception:
                            pass
            except Exception as e:
                return False, f"press failed: {e}"
        return False, "no input backend available"

    def hotkey(self, *keys: str) -> Tuple[bool, str]:
        blocked = {"alt+f4", "ctrl+alt+delete", "super+q", "ctrl+alt+t"}
        combo_str = "+".join(keys).lower()
        if combo_str in blocked:
            log.warning("Blocked unsafe key combo: %s", combo_str)
            return False, f"blocked unsafe combo: {combo_str}"

        session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
        is_wayland = session_type == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY"))

        if self._pynput_ok and not is_wayland:
            try:
                kobjs = [self._key_name_to_pynput(k) for k in keys]
                try:
                    for k in kobjs:
                        self._keyboard.press(k)
                    for k in reversed(kobjs):
                        self._keyboard.release(k)
                    time.sleep(0.12)
                    return True, f"hotkey {'+'.join(keys)}"
                finally:
                    # Safety net: ensure every key is released even if an
                    # exception is thrown mid-sequence (prevents stuck modifiers).
                    for k in reversed(kobjs):
                        try:
                            self._keyboard.release(k)
                        except Exception:
                            pass
            except Exception as e:
                return False, f"hotkey failed: {e}"
        if shutil.which("xdotool"):
            try:
                subprocess.run(["xdotool", "key", combo_str], timeout=5, check=True)
                return True, f"hotkey {'+'.join(keys)}"
            except Exception as e:
                return False, f"hotkey failed: {e}"
        # Last resort: pynput even on Wayland
        if self._pynput_ok:
            try:
                kobjs = [self._key_name_to_pynput(k) for k in keys]
                try:
                    for k in kobjs:
                        self._keyboard.press(k)
                    for k in reversed(kobjs):
                        self._keyboard.release(k)
                    time.sleep(0.12)
                    return True, f"hotkey {'+'.join(keys)} (pynput fallback)"
                finally:
                    for k in reversed(kobjs):
                        try:
                            self._keyboard.release(k)
                        except Exception:
                            pass
            except Exception as e:
                return False, f"hotkey failed: {e}"
        return False, "no input backend available"

    # ── App / Window ──────────────────────────────────────────────────────────

    def launch_app(self, app_name: str) -> str:
        if not app_name:
            return "no app specified"
        app_lower = app_name.strip().lower()
        cmd = _LINUX_APP_COMMANDS.get(app_lower, app_lower)
        try:
            subprocess.Popen([cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            time.sleep(1.5)
            return f"launched {app_name}"
        except Exception as e:
            log.error("launch_app(%r) failed: %s", app_name, e)
            return f"failed to launch {app_name}: {e}"

    def _get_chrome_profiles(self, browser_cmd: str) -> List[str]:
        """Return available Chrome/Chromium profile directory names."""
        config_home = os.getenv("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        browser_to_dir = {
            "google-chrome": os.path.join(config_home, "google-chrome"),
            "chromium-browser": os.path.join(config_home, "chromium"),
            "chromium": os.path.join(config_home, "chromium"),
            "microsoft-edge": os.path.join(config_home, "microsoft-edge"),
        }
        profile_dir = browser_to_dir.get(browser_cmd)
        if not profile_dir or not os.path.isdir(profile_dir):
            return []
        profiles = []
        for entry in os.listdir(profile_dir):
            entry_path = os.path.join(profile_dir, entry)
            if os.path.isdir(entry_path) and entry.startswith("Profile"):
                profiles.append(entry)
            elif entry == "Default" and os.path.isdir(entry_path):
                profiles.insert(0, entry)
        return profiles

    def launch_browser(self, name: str, url: Optional[str] = None, profile: Optional[str] = None) -> str:
        app_lower = name.strip().lower()
        cmd = _LINUX_APP_COMMANDS.get(app_lower, app_lower)
        cmd_list = [cmd]

        # Chrome/Chromium/Edge: add profile flag to skip profile picker
        is_chromium_like = app_lower in ("chrome", "google chrome", "chromium", "chromium-browser", "edge", "browser")
        if is_chromium_like:
            profiles = self._get_chrome_profiles(cmd)
            chosen_profile = profile or "Default"
            if chosen_profile == "Default" and "Default" not in profiles and profiles:
                chosen_profile = profiles[0]
            cmd_list.append(f"--profile-directory={chosen_profile}")
            # Suppress first-run / default-browser dialogs that also block automation
            cmd_list.extend(["--no-first-run", "--no-default-browser-check"])

        if url:
            cmd_list.append(url)
        try:
            subprocess.Popen(cmd_list, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            time.sleep(2.0)
            profile_msg = f" (profile: {chosen_profile})" if is_chromium_like and profile else ""
            return f"launched {name}{profile_msg}"
        except Exception as e:
            return f"failed to launch {name}: {e}"

    def ensure_app_open(self, app_name: str, url: Optional[str] = None, profile: Optional[str] = None) -> str:
        app_lower = app_name.lower().strip()
        from core.agent_engine import BROWSER_APPS, KNOWN_APPS
        canonical = KNOWN_APPS.get(app_lower, app_lower)
        if canonical in BROWSER_APPS or app_lower in BROWSER_APPS:
            return self.launch_browser(app_name, url, profile=profile)
        # Try to find and raise window
        try:
            result = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    parts = line.split(None, 3)
                    if len(parts) >= 4:
                        title = parts[3].lower()
                        if app_lower in title or canonical in title:
                            wid = parts[0]
                            subprocess.run(["wmctrl", "-ia", wid], capture_output=True, timeout=2)
                            time.sleep(0.5)
                            return f"raised {app_name}"
        except Exception:
            pass
        try:
            result = subprocess.run(["xdotool", "search", "--class", canonical], capture_output=True, text=True, timeout=2)
            if result.returncode == 0 and result.stdout.strip():
                wid = result.stdout.strip().split("\n")[0]
                subprocess.run(["xdotool", "windowactivate", wid], capture_output=True, timeout=2)
                time.sleep(0.5)
                return f"raised {app_name}"
        except Exception:
            pass
        return self.launch_app(app_name)

    def raise_window(self, window_id: Any) -> bool:
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

    def get_foreground_app(self) -> str:
        try:
            result = subprocess.run(["xdotool", "getactivewindow", "getwindowclassname"], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        try:
            result = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if " - Active" in line or line.endswith(" *"):
                        parts = line.split(None, 3)
                        if len(parts) >= 4:
                            return parts[3]
        except Exception:
            pass
        return ""

    def open_file(self, path: str) -> None:
        subprocess.Popen(["xdg-open", path])

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

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _key_name_to_pynput(self, key: str):
        from pynput.keyboard import Key
        mapping = {
            "ctrl": Key.ctrl, "alt": Key.alt, "shift": Key.shift,
            "win": Key.cmd, "super": Key.cmd, "cmd": Key.cmd,
            "return": Key.return_, "enter": Key.return_,
            "space": Key.space, "tab": Key.tab,
            "escape": Key.esc, "esc": Key.esc,
            "up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
            "home": Key.home, "end": Key.end,
            "pageup": Key.pageup, "pagedown": Key.pagedown,
            "delete": Key.delete, "backspace": Key.backspace,
        }
        for i in range(1, 13):
            mapping[f"f{i}"] = getattr(Key, f"f{i}")
        return mapping.get(key.lower(), key)
