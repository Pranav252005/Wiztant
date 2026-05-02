"""platforms/factory.py — Lazy platform driver factory.

Every getter imports the concrete class *inside* the function so that
importing this module on Linux does not attempt to load win32api, and
vice-versa.
"""
from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from platforms.abstract import (
        BaseHotkeys,
        BaseTTS,
        BaseVLM,
        BaseWindowMgmt,
        BaseSystemAccess,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Platform detection
# ═══════════════════════════════════════════════════════════════════════════════

_PLATFORM: str | None = None


def get_platform_name() -> str:
    """Return the canonical platform name."""
    global _PLATFORM
    if _PLATFORM is None:
        if sys.platform == "win32":
            _PLATFORM = "windows"
        elif sys.platform.startswith("linux"):
            _PLATFORM = "linux"
        else:
            raise OSError(f"Unsupported platform: {sys.platform}")
    return _PLATFORM


# ═══════════════════════════════════════════════════════════════════════════════
# Lazy factory getters
# ═══════════════════════════════════════════════════════════════════════════════


def get_hotkeys() -> "BaseHotkeys":
    """Return the platform-specific hotkey driver."""
    platform = get_platform_name()
    if platform == "linux":
        from platforms.linux.hotkeys import LinuxHotkeys
        return LinuxHotkeys()
    else:
        from platforms.windows.hotkeys import WindowsHotkeys
        return WindowsHotkeys()


def get_tts() -> "BaseTTS":
    """Return the platform-specific TTS driver."""
    platform = get_platform_name()
    if platform == "linux":
        from platforms.linux.tts import LinuxTTS
        return LinuxTTS()
    else:
        from platforms.windows.tts import WindowsTTS
        return WindowsTTS()


def get_vlm() -> "BaseVLM":
    """Return the platform-specific VLM driver."""
    platform = get_platform_name()
    if platform == "linux":
        from platforms.linux.vlm import LinuxVLM
        return LinuxVLM()
    else:
        from platforms.windows.vlm import WindowsVLM
        return WindowsVLM()


def get_window_mgmt() -> "BaseWindowMgmt":
    """Return the platform-specific window management driver."""
    platform = get_platform_name()
    if platform == "linux":
        from platforms.linux.window_mgmt import LinuxWindowMgmt
        return LinuxWindowMgmt()
    else:
        from platforms.windows.window_mgmt import WindowsWindowMgmt
        return WindowsWindowMgmt()


def get_system_access() -> "BaseSystemAccess":
    """Return the platform-specific system access driver."""
    platform = get_platform_name()
    if platform == "linux":
        from platforms.linux.system_access import LinuxSystemAccess
        return LinuxSystemAccess()
    else:
        from platforms.windows.system_access import WindowsSystemAccess
        return WindowsSystemAccess()


def get_agent_runtime():
    """Return the platform-specific agent runtime (hands for unified agent)."""
    platform = get_platform_name()
    if platform == "linux":
        from platforms.linux.agent_runtime import LinuxAgentRuntime
        return LinuxAgentRuntime()
    else:
        from platforms.windows.agent_runtime import WindowsAgentRuntime
        return WindowsAgentRuntime()
