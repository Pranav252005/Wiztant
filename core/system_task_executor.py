"""
Whiztant core/system_task_executor.py — System-level task execution for background agent.

Handles operations that go beyond browser automation:
  - Registry Editor (HKLM / HKCU modifications)
  - Windows Settings app (toggle/change settings)
  - NVIDIA Control Panel (GPU settings)
  - Game optimization workflows (launcher + in-game + GPU + registry)
  - General system apps (Control Panel, Device Manager, Disk Cleanup)
  - PowerShell / command-line tasks

Each executor launches the target app in a minimized window, then hands control
to the VLM agent loop (screenshot → decision → isolated PostMessage action).
"""

import os
import re
import json
import asyncio
import subprocess
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

# Win32 imports (graceful fallback)
try:
    import win32gui
    import win32con
    _WIN32 = True
except ImportError:
    _WIN32 = False

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ── App launch helpers ──────────────────────────────────────────────────────

# Common app paths / URI schemes for Windows system apps
_APP_LAUNCH_MAP = {
    "regedit":       {"cmd": "regedit.exe",       "wait": 2.0},
    "settings":      {"uri": "ms-settings:",       "wait": 2.0},
    "nvidia":        {"paths": [
        r"C:\Program Files\NVIDIA Corporation\NVIDIA Control Panel\nvcplui.exe",
        r"C:\Windows\System32\nvcplui.exe",
    ], "wait": 3.0},
    "devmgmt":       {"cmd": "mmc devmgmt.msc",   "wait": 2.0},
    "control":       {"cmd": "control.exe",        "wait": 2.0},
    "cleanmgr":      {"cmd": "cleanmgr.exe",       "wait": 3.0},
    "taskmgr":       {"cmd": "taskmgr.exe",         "wait": 1.5},
    "powershell":    {"cmd": "powershell.exe",      "wait": 1.0},
    "cmd":           {"cmd": "cmd.exe",             "wait": 1.0},
    "sound":         {"uri": "ms-settings:sound",   "wait": 2.0},
    "display":       {"uri": "ms-settings:display", "wait": 2.0},
    "gaming":        {"uri": "ms-settings:gaming-gamebar", "wait": 2.0},
    "startup":       {"uri": "ms-settings:startupapps",    "wait": 2.0},
    "power":         {"uri": "ms-settings:powersleep",     "wait": 2.0},
    "privacy":       {"uri": "ms-settings:privacy",        "wait": 2.0},
}

# Settings URI shortcuts for common user requests
_SETTINGS_URI_MAP = {
    "gpu acceleration":  "ms-settings:display-advancedgraphics",
    "game mode":         "ms-settings:gaming-gamemode",
    "game bar":          "ms-settings:gaming-gamebar",
    "startup apps":      "ms-settings:startupapps",
    "startup programs":  "ms-settings:startupapps",
    "power plan":        "ms-settings:powersleep",
    "power settings":    "ms-settings:powersleep",
    "display":           "ms-settings:display",
    "refresh rate":      "ms-settings:display",
    "night light":       "ms-settings:nightlight",
    "sound":             "ms-settings:sound",
    "notifications":     "ms-settings:notifications",
    "privacy":           "ms-settings:privacy",
    "bluetooth":         "ms-settings:bluetooth",
    "wifi":              "ms-settings:network-wifi",
    "vpn":               "ms-settings:network-vpn",
    "storage":           "ms-settings:storagesense",
    "mouse":             "ms-settings:mousetouchpad",
    "keyboard":          "ms-settings:typing",
}


async def _launch_app(
    app_key: str,
    extra_args: Optional[List[str]] = None,
) -> Tuple[Optional[int], Optional[int]]:
    """
    Launch a system app by key. Returns (pid, window_handle).
    For URI-based apps (Settings), pid may be None.
    """
    from core.agent_isolation import find_window_by_pid, minimize_window

    info = _APP_LAUNCH_MAP.get(app_key)
    if not info:
        return None, None

    wait_time = info.get("wait", 2.0)
    pid = None
    hwnd = None

    # URI-based launch (Settings app)
    if "uri" in info:
        uri = info["uri"]
        os.startfile(uri)
        await asyncio.sleep(wait_time)
        # Settings doesn't give us a direct PID; find window by title
        hwnd = _find_window_by_title_substring("Settings")
        if hwnd:
            minimize_window(hwnd)
        return None, hwnd

    # Command-based launch
    cmd = info.get("cmd", "")

    # Check explicit paths (e.g. NVIDIA)
    if "paths" in info:
        for p in info["paths"]:
            if os.path.exists(p):
                cmd = p
                break
        else:
            # NVIDIA not found at known paths, try Start Menu
            cmd = info["paths"][0]

    args = cmd.split() if " " in cmd else [cmd]
    if extra_args:
        args.extend(extra_args)

    try:
        proc = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        pid = proc.pid
    except FileNotFoundError:
        return None, None

    await asyncio.sleep(wait_time)

    # Find window by PID
    if pid:
        hwnd = find_window_by_pid(pid)
        if hwnd:
            minimize_window(hwnd)

    return pid, hwnd


def _find_window_by_title_substring(substring: str) -> Optional[int]:
    """Find a visible window whose title contains the given substring."""
    if not _WIN32:
        return None

    result = []

    def _enum(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if substring.lower() in title.lower():
                result.append(hwnd)
        return True

    win32gui.EnumWindows(_enum, None)
    return result[0] if result else None


# ── System Task Executor ────────────────────────────────────────────────────

class SystemTaskExecutor:
    """
    Executes system-level tasks that require launching Windows apps
    (Registry Editor, Settings, NVIDIA Control Panel, etc.)
    and driving them with the VLM agent loop via isolated input.
    """

    def __init__(self):
        self._active_pids: List[int] = []

    # ── Registry tasks ──────────────────────────────────────────────────────

    async def execute_registry_task(
        self,
        task,
        vlm_loop_fn,
    ) -> Dict[str, Any]:
        """
        Launch regedit and let VLM navigate to the target key/value.
        vlm_loop_fn: async callable(task, hwnd) -> result dict
        """
        result = {"status": "success", "changes": []}

        pid, hwnd = await _launch_app("regedit")
        if not hwnd:
            return {"status": "error", "error": "Could not launch Registry Editor"}

        if pid:
            self._active_pids.append(pid)

        try:
            task.status = "executing (registry)"
            loop_result = await vlm_loop_fn(task, hwnd)
            result.update(loop_result)
            result["changes"].append(f"Registry: {task.description}")
        except Exception as e:
            result = {"status": "error", "error": str(e)}
        finally:
            self._close_window(hwnd)
            if pid and pid in self._active_pids:
                self._active_pids.remove(pid)

        return result

    # ── Windows Settings tasks ──────────────────────────────────────────────

    async def execute_windows_settings_task(
        self,
        task,
        vlm_loop_fn,
    ) -> Dict[str, Any]:
        """
        Open the Settings app (jumping to the right page if possible)
        and let VLM make the change.
        """
        result = {"status": "success", "setting": task.description}

        # Try to open the most specific settings page
        uri = self._match_settings_uri(task.description)
        if uri:
            os.startfile(uri)
            await asyncio.sleep(2.0)
            hwnd = _find_window_by_title_substring("Settings")
        else:
            _, hwnd = await _launch_app("settings")

        if not hwnd:
            return {"status": "error", "error": "Could not open Windows Settings"}

        try:
            task.status = "executing (settings)"
            loop_result = await vlm_loop_fn(task, hwnd)
            result.update(loop_result)
        except Exception as e:
            result = {"status": "error", "error": str(e)}
        finally:
            self._close_window(hwnd)

        return result

    def _match_settings_uri(self, description: str) -> Optional[str]:
        """Try to match the task description to a specific ms-settings: URI."""
        desc_lower = description.lower()
        for keyword, uri in _SETTINGS_URI_MAP.items():
            if keyword in desc_lower:
                return uri
        return None

    # ── NVIDIA Control Panel tasks ──────────────────────────────────────────

    async def execute_nvidia_task(
        self,
        task,
        vlm_loop_fn,
    ) -> Dict[str, Any]:
        """Launch NVIDIA Control Panel and let VLM change GPU settings."""
        result = {"status": "success", "gpu_settings": []}

        pid, hwnd = await _launch_app("nvidia")
        if not hwnd:
            # Fallback: try opening via desktop right-click context menu or start menu
            hwnd = _find_window_by_title_substring("NVIDIA Control Panel")
            if not hwnd:
                return {"status": "error", "error": "Could not open NVIDIA Control Panel"}

        if pid:
            self._active_pids.append(pid)

        try:
            task.status = "executing (nvidia)"
            loop_result = await vlm_loop_fn(task, hwnd)
            result.update(loop_result)
            result["gpu_settings"].append(task.description)
        except Exception as e:
            result = {"status": "error", "error": str(e)}
        finally:
            self._close_window(hwnd)
            if pid and pid in self._active_pids:
                self._active_pids.remove(pid)

        return result

    # ── Game optimization workflow ──────────────────────────────────────────

    async def execute_game_optimization(
        self,
        task,
        vlm_loop_fn,
    ) -> Dict[str, Any]:
        """
        Multi-step game optimization:
        1. Apply registry tweaks (direct, no GUI needed)
        2. Open NVIDIA Control Panel → change GPU settings
        3. Open game launcher → change in-game settings (if applicable)
        """
        result = {
            "status": "success",
            "actions_taken": [],
            "settings_changed": [],
        }

        # Parse game name and target FPS from description
        game_name, target_fps = self._parse_game_task(task.description)

        # Step 1: Registry optimizations (direct, no VLM needed)
        task.status = "executing (registry tweaks)"
        reg_changes = await self._apply_gaming_registry_tweaks()
        result["actions_taken"].append("Applied gaming registry optimizations")
        result["settings_changed"].extend(reg_changes)

        # Step 2: NVIDIA Control Panel (needs VLM)
        task.status = "executing (NVIDIA settings)"
        pid, hwnd = await _launch_app("nvidia")
        if hwnd:
            try:
                nvidia_result = await vlm_loop_fn(task, hwnd)
                result["actions_taken"].append("Changed NVIDIA Control Panel settings")
                if nvidia_result.get("data"):
                    result["settings_changed"].append(str(nvidia_result["data"]))
            except Exception as e:
                result["actions_taken"].append(f"NVIDIA settings skipped: {e}")
            finally:
                self._close_window(hwnd)

        # Step 3: Game settings via launcher (if we can find it)
        if game_name:
            task.status = f"executing (game settings: {game_name})"
            steam_hwnd = _find_window_by_title_substring("Steam")
            if steam_hwnd:
                try:
                    game_result = await vlm_loop_fn(task, steam_hwnd)
                    result["actions_taken"].append(f"Changed {game_name} settings via Steam")
                    if game_result.get("data"):
                        result["settings_changed"].append(str(game_result["data"]))
                except Exception:
                    pass

        summary_parts = [f"Optimized for gaming"]
        if target_fps:
            summary_parts.append(f"target {target_fps} FPS")
        if game_name:
            summary_parts.append(f"game: {game_name}")
        result["summary"] = " | ".join(summary_parts)

        return result

    def _parse_game_task(self, description: str) -> Tuple[Optional[str], Optional[int]]:
        """Extract game name and target FPS from task description."""
        game_name = None
        target_fps = None

        fps_match = re.search(r"(\d+)\s*fps", description, re.IGNORECASE)
        if fps_match:
            target_fps = int(fps_match.group(1))

        # "Optimize <game> for ..."
        game_match = re.search(
            r"(?:optimize|tune|tweak)\s+(.+?)\s+(?:for|to|at)",
            description,
            re.IGNORECASE,
        )
        if game_match:
            game_name = game_match.group(1).strip()

        return game_name, target_fps

    async def _apply_gaming_registry_tweaks(self) -> List[str]:
        """
        Apply well-known registry optimizations for gaming.
        Uses reg.exe directly — no GUI needed.
        """
        changes = []
        tweaks = [
            # Disable Game DVR (reduces overhead)
            (r"HKCU\System\GameConfigStore", "GameDVR_Enabled", "REG_DWORD", "0"),
            (r"HKLM\SOFTWARE\Policies\Microsoft\Windows\GameDVR", "AllowGameDVR", "REG_DWORD", "0"),
            # Disable full-screen optimizations system-wide
            (r"HKCU\System\GameConfigStore", "GameDVR_FSEBehaviorMode", "REG_DWORD", "2"),
            # GPU scheduling (Hardware-accelerated GPU scheduling)
            (r"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode", "REG_DWORD", "2"),
            # Disable Nagle's algorithm for lower latency
            (r"HKLM\SOFTWARE\Microsoft\MSMQ\Parameters", "TCPNoDelay", "REG_DWORD", "1"),
        ]

        for path, name, vtype, value in tweaks:
            try:
                cmd = f'reg add "{path}" /v {name} /t {vtype} /d {value} /f'
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.wait()
                if proc.returncode == 0:
                    changes.append(f"{path}\\{name} = {value}")
            except Exception:
                pass

        return changes

    # ── General system tasks ────────────────────────────────────────────────

    async def execute_system_task(
        self,
        task,
        vlm_loop_fn,
    ) -> Dict[str, Any]:
        """
        Execute a general system task: Control Panel, Device Manager,
        Disk Cleanup, Task Manager, etc.
        """
        result = {"status": "success", "task": task.description}

        app_key = self._detect_system_app(task.description)
        if not app_key:
            return {"status": "error", "error": f"Could not determine which app to open for: {task.description}"}

        pid, hwnd = await _launch_app(app_key)
        if not hwnd:
            # Fallback: try title-based search
            title_map = {
                "control":  "Control Panel",
                "devmgmt":  "Device Manager",
                "cleanmgr": "Disk Cleanup",
                "taskmgr":  "Task Manager",
            }
            title = title_map.get(app_key)
            if title:
                hwnd = _find_window_by_title_substring(title)
            if not hwnd:
                return {"status": "error", "error": f"Could not open {app_key}"}

        if pid:
            self._active_pids.append(pid)

        try:
            task.status = f"executing ({app_key})"
            loop_result = await vlm_loop_fn(task, hwnd)
            result.update(loop_result)
        except Exception as e:
            result = {"status": "error", "error": str(e)}
        finally:
            self._close_window(hwnd)
            if pid and pid in self._active_pids:
                self._active_pids.remove(pid)

        return result

    def _detect_system_app(self, description: str) -> Optional[str]:
        """Detect which system app to open from the task description."""
        d = description.lower()

        if any(w in d for w in ["control panel", "uninstall", "programs and features"]):
            return "control"
        if any(w in d for w in ["device manager", "driver", "devmgmt"]):
            return "devmgmt"
        if any(w in d for w in ["disk cleanup", "temp files", "clear cache", "free space"]):
            return "cleanmgr"
        if any(w in d for w in ["task manager", "processes", "end task"]):
            return "taskmgr"
        if any(w in d for w in ["powershell", "ps command", "ps1"]):
            return "powershell"
        if any(w in d for w in ["command prompt", "cmd", "batch"]):
            return "cmd"
        if any(w in d for w in ["sound", "audio", "speaker", "microphone"]):
            return "sound"
        if any(w in d for w in ["display", "resolution", "refresh rate", "monitor"]):
            return "display"

        return None

    # ── PowerShell direct execution ─────────────────────────────────────────

    async def execute_powershell_command(self, command: str) -> Dict[str, Any]:
        """
        Execute a PowerShell command directly (no VLM needed).
        For simple system commands that don't require GUI interaction.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)

            return {
                "status": "success" if proc.returncode == 0 else "error",
                "data": stdout.decode("utf-8", errors="replace").strip(),
                "error": stderr.decode("utf-8", errors="replace").strip() if proc.returncode != 0 else None,
            }
        except asyncio.TimeoutError:
            return {"status": "error", "error": "Command timed out after 30 seconds"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ── Cleanup ─────────────────────────────────────────────────────────────

    def _close_window(self, hwnd: Optional[int]):
        """Close a window gracefully via WM_CLOSE."""
        if hwnd and _WIN32:
            try:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            except Exception:
                pass

    def cleanup_all(self):
        """Kill all processes opened by this executor."""
        import psutil
        for pid in self._active_pids:
            try:
                proc = psutil.Process(pid)
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                pass
        self._active_pids.clear()
