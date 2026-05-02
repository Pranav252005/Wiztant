"""Whiztant Platform Abstraction Layer (PAL)."""
from platforms.factory import (
    get_hotkeys,
    get_platform_name,
    get_system_access,
    get_tts,
    get_vlm,
    get_window_mgmt,
)

__all__ = [
    "get_platform_name",
    "get_hotkeys",
    "get_tts",
    "get_vlm",
    "get_window_mgmt",
    "get_system_access",
]
