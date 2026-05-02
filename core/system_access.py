"""
Wiztant core/system_access.py — System mutation with full undo support.

Every function that modifies OS state calls _log_change(), which pushes
a structured entry onto data/undo_stack.json.  undo_last() pops the top
entry and reverses it based on its category.

Categories
──────────
  REGISTRY      – any winreg write (game mode, HAGS, visual effects, etc.)
  POWER_PROFILE – powercfg /setactive
  STARTUP       – HKCU\\…\\Run add or remove
  PROCESS       – psutil priority change  (best-effort, non-reversible)
  APP_LAUNCH    – open_app / browser  (cannot undo)

Undo stack is capped at STACK_LIMIT = 50 entries (oldest dropped).
"""

import os
import json
import sys
import subprocess
import psutil
import ctypes
from datetime import datetime
from pathlib import Path
from typing import Optional

# Windows-only imports
if sys.platform == "win32":
    import winreg
else:
    winreg = None

# ── Tier constants ────────────────────────────────────────────────────────────
TIER_STANDARD = "standard"
TIER_SYSTEM   = "system"
TIER_DEEP     = "deep"

CHANGES_LOG = Path("data/system_changes.log")
UNDO_STACK  = Path("data/undo_stack.json")
STACK_LIMIT = 50

# ── Hive map ──────────────────────────────────────────────────────────────────
if sys.platform == "win32":
    HIVE_MAP = {
        "HKCU": winreg.HKEY_CURRENT_USER,
        "HKLM": winreg.HKEY_LOCAL_MACHINE,
        "HKCR": winreg.HKEY_CLASSES_ROOT,
    }
else:
    HIVE_MAP = {}


# ── TTS helper (lazy import to avoid circular) ────────────────────────────────
def _speak(text: str):
    """Speak text via the platform TTS driver (Kokoro)."""
    try:
        from platforms.factory import get_tts
        tts = get_tts()
        tts.speak(text, blocking=False)
    except Exception as e:
        print(f"[TTS] Speak failed: {e}")


# ── Registry helpers ──────────────────────────────────────────────────────────

def _registry_get(hive: str, path: str, name: str):
    """Read a registry value. Returns None if not found."""
    if sys.platform != "win32" or winreg is None:
        return None
    try:
        key = winreg.OpenKey(HIVE_MAP[hive], path, 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, name)
        winreg.CloseKey(key)
        return value
    except Exception:
        return None


def _registry_set(hive: str, path: str, name: str, value_type: int, value):
    """Write a registry value. Creates the key path if it doesn't exist."""
    if sys.platform != "win32" or winreg is None:
        return
    key = winreg.CreateKeyEx(HIVE_MAP[hive], path, 0, winreg.KEY_SET_VALUE)
    winreg.SetValueEx(key, name, 0, value_type, value)
    winreg.CloseKey(key)


def _registry_delete(hive: str, path: str, name: str):
    """Delete a registry value. Silently ignores if already gone."""
    if sys.platform != "win32" or winreg is None:
        return
    try:
        key = winreg.OpenKey(HIVE_MAP[hive], path, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, name)
        winreg.CloseKey(key)
    except FileNotFoundError:
        pass
    except Exception:
        pass


# ── Undo stack ────────────────────────────────────────────────────────────────

def load_undo_stack() -> list:
    if not UNDO_STACK.exists():
        return []
    try:
        return json.loads(UNDO_STACK.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_undo_stack(stack: list):
    UNDO_STACK.parent.mkdir(parents=True, exist_ok=True)
    UNDO_STACK.write_text(json.dumps(stack, indent=2), encoding="utf-8")


# ── Change logger ─────────────────────────────────────────────────────────────

def _log_change(action: str, location: str, old_value, new_value,
                undo_cmd: dict = None):
    """
    Append one entry to the human-readable log and the undo stack.
    The undo_cmd dict must contain at least {"category": "REGISTRY"|…}.
    Stack is capped at STACK_LIMIT; oldest entry is dropped when full.
    """
    CHANGES_LOG.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "action":    action,
        "location":  location,
        "old_value": str(old_value) if old_value is not None else None,
        "new_value": str(new_value),
        "undo_cmd":  undo_cmd,
    }

    with open(CHANGES_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{entry['timestamp']}] {action} | {location} | "
                f"{old_value} → {new_value}\n")

    stack = load_undo_stack()
    stack.append(entry)
    if len(stack) > STACK_LIMIT:
        stack = stack[-STACK_LIMIT:]   # drop oldest
    save_undo_stack(stack)


# Backward-compatible alias (old callers used log_change)
log_change = _log_change


# ── Core undo logic ───────────────────────────────────────────────────────────

def undo_last() -> str:
    """
    Pop the most recent entry from the undo stack and reverse it.
    Speaks the result via TTS and returns the status string.

    Category dispatch:
      REGISTRY      → restore old DWORD/SZ value (or delete if old was None)
      POWER_PROFILE → powercfg /setactive <old_guid>
      STARTUP       → restore or delete the Run key entry
      APP_LAUNCH    → skip (cannot undo)
      PROCESS       → best-effort subprocess
    """
    stack = load_undo_stack()
    if not stack:
        msg = "Nothing to undo."
        _speak(msg)
        return msg

    last  = stack.pop()
    save_undo_stack(stack)

    action = last.get("action", "unknown action")
    undo   = last.get("undo_cmd")

    if not undo:
        msg = f"Cannot auto-undo: {action}"
        _speak(msg)
        return msg

    category = undo.get("category", undo.get("type", ""))

    try:
        if category == "REGISTRY":
            old = undo.get("old_value")
            if old is None:
                # The key didn't exist before — delete it to restore prior state
                _registry_delete(undo["hive"], undo["path"], undo["name"])
            else:
                _registry_set(undo["hive"], undo["path"], undo["name"],
                              undo["value_type"], old)
            msg = f"Undone: {action}"

        elif category == "STARTUP":
            old = undo.get("old_value")
            name = undo.get("name", "")
            path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            if old is None:
                # Was a new addition — removing it restores prior state
                _registry_delete("HKCU", path, name)
                msg = f"Undone: {action} — entry removed from startup"
            else:
                # Was a deletion — re-add the entry
                _registry_set("HKCU", path, name, winreg.REG_SZ, old)
                msg = f"Undone: {action} — entry restored to startup"

        elif category == "POWER_PROFILE":
            old_guid = undo.get("old_guid", "")
            if not old_guid or old_guid == "unknown":
                msg = f"Cannot undo: original power plan GUID was not recorded"
            else:
                subprocess.run(
                    f"powercfg /setactive {old_guid}",
                    shell=True, capture_output=True,
                )
                msg = f"Undone: {action}"

        elif category == "APP_LAUNCH":
            msg = f"Cannot undo app launch: {action}"

        elif category == "PROCESS":
            # Best-effort: wmic is deprecated on Windows 11 but still functional
            cmd = undo.get("cmd", "")
            if cmd:
                subprocess.run(cmd, shell=True, capture_output=True)
                msg = f"Undone: {action} (process priority restored)"
            else:
                msg = f"Cannot undo process change: no command recorded"

        # Legacy undo_cmd types from older stack entries
        elif category == "registry":
            old = undo.get("old_value")
            if old is None:
                _registry_delete(undo["hive"], undo["path"], undo["name"])
            else:
                _registry_set(undo["hive"], undo["path"], undo["name"],
                              undo["value_type"], old)
            msg = f"Undone: {action}"

        elif category == "power_plan":
            old_guid = undo.get("old_guid", "")
            if old_guid and old_guid != "unknown":
                subprocess.run(f"powercfg /setactive {old_guid}",
                               shell=True, capture_output=True)
                msg = f"Undone: {action}"
            else:
                msg = f"Cannot undo: original GUID not recorded"

        elif category == "subprocess":
            subprocess.run(undo.get("cmd", ""), shell=True, capture_output=True)
            msg = f"Undone: {action}"

        else:
            msg = f"Cannot undo: unknown category '{category}'"

    except Exception as e:
        msg = f"Undo failed: {e}"

    _speak(msg)
    return msg


def undo_last_action() -> str:
    """Backward-compatible alias for undo_last()."""
    return undo_last()


def undo_all_actions() -> str:
    """Undo every entry on the stack, oldest last."""
    if not load_undo_stack():
        return "No changes to undo."
    results = []
    while load_undo_stack():
        results.append(undo_last())
    return "\n".join(results)


# ── Convenience writer (logs with REGISTRY category) ─────────────────────────

def registry_write(hive: str, path: str, name: str,
                   value_type: int, new_value,
                   description: str = "") -> str:
    """Write a registry value and push a REGISTRY undo entry."""
    old_value = _registry_get(hive, path, name)
    _registry_set(hive, path, name, value_type, new_value)
    _log_change(
        action   = description or f"Registry: {name}",
        location = f"{hive}\\{path}",
        old_value= old_value,
        new_value= new_value,
        undo_cmd = {
            "category":   "REGISTRY",
            "hive":       hive,
            "path":       path,
            "name":       name,
            "value_type": value_type,
            "old_value":  old_value,
        },
    )
    return f"Set {name} = {new_value}"


# ── SYSTEM tier ───────────────────────────────────────────────────────────────

def set_power_plan(plan: str) -> str:
    """Switch power plan.  plan: 'balanced' | 'performance' | 'power_saver'"""
    plans = {
        "balanced":    "381b4222-f694-41f0-9685-ff5bb260df2e",
        "performance": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
        "power_saver": "a1841308-3541-4fab-bc81-f71556f20b4a",
    }
    guid = plans.get(plan)
    if not guid:
        return f"Unknown plan: {plan}. Use balanced, performance, or power_saver."

    result  = subprocess.run("powercfg /getactivescheme",
                             shell=True, capture_output=True, text=True)
    parts   = result.stdout.strip().split()
    old_guid = parts[3] if len(parts) > 3 else "unknown"

    subprocess.run(f"powercfg /setactive {guid}", shell=True, capture_output=True)
    _log_change(
        action   = f"Set power plan to {plan}",
        location = "Power Options",
        old_value= old_guid,
        new_value= guid,
        undo_cmd = {"category": "POWER_PROFILE", "old_guid": old_guid},
    )
    return f"Power plan set to {plan}"


def set_process_priority(process_name: str, priority: str = "high") -> str:
    """
    Boost a running process.  priority: 'low' | 'normal' | 'high' | 'realtime'
    Logs each matching PID with a PROCESS undo entry (best-effort via wmic).
    """
    priority_map = {
        "low":      psutil.IDLE_PRIORITY_CLASS,
        "normal":   psutil.NORMAL_PRIORITY_CLASS,
        "high":     psutil.HIGH_PRIORITY_CLASS,
        "realtime": psutil.REALTIME_PRIORITY_CLASS,
    }
    p_class = priority_map.get(priority, psutil.HIGH_PRIORITY_CLASS)
    found   = []

    for proc in psutil.process_iter(["name", "pid"]):
        if process_name.lower() in proc.info["name"].lower():
            try:
                p   = psutil.Process(proc.info["pid"])
                old = p.nice()
                p.nice(p_class)
                found.append(proc.info["pid"])
                _log_change(
                    action   = f"Set {proc.info['name']} priority to {priority}",
                    location = f"Process PID {proc.info['pid']}",
                    old_value= old,
                    new_value= p_class,
                    undo_cmd = {
                        "category": "PROCESS",
                        "cmd": (f"wmic process where ProcessId={proc.info['pid']}"
                                f" CALL setpriority {old}"),
                    },
                )
            except Exception:
                pass

    if not found:
        return f"{process_name} is not running."
    return f"Boosted {len(found)} {process_name} process(es) to {priority}"


# ── DEEP tier ─────────────────────────────────────────────────────────────────

def enable_game_mode() -> str:
    return registry_write(
        "HKCU", r"Software\Microsoft\GameBar",
        "AutoGameModeEnabled", winreg.REG_DWORD, 1,
        "Enable Windows Game Mode",
    )


def disable_game_mode() -> str:
    return registry_write(
        "HKCU", r"Software\Microsoft\GameBar",
        "AutoGameModeEnabled", winreg.REG_DWORD, 0,
        "Disable Windows Game Mode",
    )


def disable_game_bar() -> str:
    return registry_write(
        "HKCU", r"Software\Microsoft\GameBar",
        "UseNexusForGameBarEnabled", winreg.REG_DWORD, 0,
        "Disable Xbox Game Bar",
    )


def enable_hardware_accelerated_gpu_scheduling() -> str:
    return registry_write(
        "HKLM",
        r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers",
        "HwSchMode", winreg.REG_DWORD, 2,
        "Enable Hardware Accelerated GPU Scheduling (HAGS)",
    )


def set_visual_effects_performance() -> str:
    return registry_write(
        "HKCU",
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects",
        "VisualFXSetting", winreg.REG_DWORD, 2,
        "Set visual effects to Best Performance",
    )


def disable_startup_program(program_name: str) -> str:
    """
    Remove a program from HKCU Run.
    Logs a STARTUP entry so undo can restore the exact command string.
    """
    path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    old  = _registry_get("HKCU", path, program_name)
    if old is None:
        return f"{program_name} not found in startup."
    try:
        _registry_delete("HKCU", path, program_name)
        _log_change(
            action   = f"Removed {program_name} from startup",
            location = f"HKCU\\{path}",
            old_value= old,
            new_value= "(removed)",
            undo_cmd = {
                "category":  "STARTUP",
                "name":      program_name,
                "old_value": old,   # not None → undo will re-add
            },
        )
        return f"Removed {program_name} from startup"
    except Exception as e:
        return f"Failed to remove {program_name}: {e}"


def add_startup_program(program_name: str, command: str) -> str:
    """
    Add a program to HKCU Run.
    Logs a STARTUP entry so undo can delete it (old_value=None signals new addition).
    """
    path     = r"Software\Microsoft\Windows\CurrentVersion\Run"
    existing = _registry_get("HKCU", path, program_name)
    _registry_set("HKCU", path, program_name, winreg.REG_SZ, command)
    _log_change(
        action   = f"Added {program_name} to startup",
        location = f"HKCU\\{path}",
        old_value= existing,
        new_value= command,
        undo_cmd = {
            "category":  "STARTUP",
            "name":      program_name,
            "old_value": existing,   # None if brand new → undo will delete
        },
    )
    return f"Added {program_name} to startup"


# ── Agent task undo ──────────────────────────────────────────────────────────

def execute_agent_undo(undo_id: str) -> bool:
    """
    Reverse an agent task by executing its recorded undo actions in reverse order.
    Reads from data/undo_actions.json (written by AgentMemory.store_undo_actions).
    Returns True on success.
    """
    import keyboard as _keyboard

    undo_file = Path("data/undo_actions.json")
    if not undo_file.exists():
        _speak(f"No undo data found for {undo_id}")
        return False

    try:
        with open(undo_file, "r", encoding="utf-8") as f:
            undo_map = json.load(f)
    except Exception as e:
        _speak(f"Could not read undo data: {e}")
        return False

    if undo_id not in undo_map:
        _speak(f"Undo ID not found: {undo_id}")
        return False

    actions = undo_map[undo_id].get("actions", [])

    for action in reversed(actions):
        undo_action = action.get("undo_action", "none")

        if undo_action == "close_window":
            app = action.get("app", "")
            if app:
                try:
                    subprocess.run(
                        f'taskkill /f /im "{app}"',
                        shell=True, capture_output=True,
                    )
                except Exception:
                    pass

        elif undo_action == "clear_text":
            try:
                _keyboard.send("ctrl+a")
                _keyboard.send("delete")
            except Exception:
                pass

        elif undo_action == "none":
            pass

    _speak(f"Undone agent task: {undo_id}")
    return True


def get_last_agent_undo_id() -> Optional[str]:
    """Return the most recent agent undo ID from task history, if any."""
    try:
        from core.agent import agent_memory
        stack = agent_memory.memory.get("undo_stack", [])
        return stack[-1] if stack else None
    except Exception:
        return None


# ── Access tier guard ─────────────────────────────────────────────────────────

def check_access(required_tier: str, current_tier: str) -> bool:
    order = [TIER_STANDARD, TIER_SYSTEM, TIER_DEEP]
    return order.index(current_tier) >= order.index(required_tier)


def get_access_tier() -> str:
    return os.getenv("SYSTEM_ACCESS_TIER", TIER_STANDARD)
