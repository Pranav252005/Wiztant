"""
core/agent_v2_profiles.py — App profiles for the Bridge Agent.

Each profile defines how to detect, focus, and interact with a target application.
The Bridge Agent uses these profiles to switch between apps during multi-app workflows.
"""
from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

log = logging.getLogger("core.agent_v2_profiles")


# =============================================================
#  APP PROFILE
# =============================================================

@dataclass
class AppProfile:
    """Profile for a desktop application that the Bridge Agent can control."""

    name: str
    display_name: str
    executable_names: List[str] = field(default_factory=list)
    window_title_patterns: List[str] = field(default_factory=list)
    url_patterns: List[str] = field(default_factory=list)
    focus_method: str = "window_title"  # window_title | executable | url
    launch_command: Optional[str] = None
    type_method: str = "type_text"  # type_text | paste

    def match_window_title(self, title: str) -> bool:
        """Check if a window title matches this app profile."""
        title_lower = title.lower()
        return any(p.lower() in title_lower for p in self.window_title_patterns)

    def match_executable(self, proc_name: str) -> bool:
        """Check if a process name matches this app profile."""
        proc_lower = proc_name.lower()
        return any(e.lower() in proc_lower for e in self.executable_names)


# =============================================================
#  BUILT-IN PROFILES
# =============================================================

BUILTIN_PROFILES: List[AppProfile] = [
    AppProfile(
        name="terminal",
        display_name="Terminal",
        executable_names=["gnome-terminal", "konsole", "kitty", "alacritty", "wezterm", "warp", "warp-terminal", "tabby", "terminator", "xterm", "ghostty"],
        window_title_patterns=["terminal", "warp", "kitty", "alacritty", "konsole", "gnome-terminal", "bash", "zsh", "fish", "powershell"],
        launch_command="gnome-terminal" if subprocess.run(["which", "gnome-terminal"], capture_output=True).returncode == 0 else "xterm",
    ),
    AppProfile(
        name="cursor",
        display_name="Cursor",
        executable_names=["cursor", "cursor.app"],
        window_title_patterns=["cursor", " - cursor"],
        launch_command="cursor",
    ),
    AppProfile(
        name="vscode",
        display_name="VS Code",
        executable_names=["code", "code-oss", "vscodium"],
        window_title_patterns=["visual studio code", " - vscode", "vscodium"],
        launch_command="code",
    ),
    AppProfile(
        name="windsurf",
        display_name="Windsurf",
        executable_names=["windsurf"],
        window_title_patterns=["windsurf"],
        launch_command="windsurf",
    ),
    AppProfile(
        name="browser",
        display_name="Browser",
        executable_names=["chrome", "chromium", "firefox", "brave", "edge", "opera", "vivaldi", "safari"],
        window_title_patterns=["chrome", "chromium", "firefox", "brave", "edge", "opera", "vivaldi", "safari"],
        url_patterns=["http://", "https://"],
        focus_method="window_title",
        launch_command="xdg-open" if subprocess.run(["which", "xdg-open"], capture_output=True).returncode == 0 else None,
    ),
    AppProfile(
        name="github",
        display_name="GitHub",
        executable_names=["chrome", "chromium", "firefox", "brave", "edge"],
        window_title_patterns=["github"],
        url_patterns=["github.com"],
        focus_method="url",
        launch_command="xdg-open https://github.com",
    ),
    AppProfile(
        name="figma",
        display_name="Figma",
        executable_names=["figma", "figma-linux", "figma-app"],
        window_title_patterns=["figma"],
        launch_command="figma",
    ),
    AppProfile(
        name="slack",
        display_name="Slack",
        executable_names=["slack"],
        window_title_patterns=["slack"],
        launch_command="slack",
    ),
    AppProfile(
        name="notion",
        display_name="Notion",
        executable_names=["notion", "notion-app", "notion-app-enhanced"],
        window_title_patterns=["notion"],
        launch_command="notion",
    ),
    AppProfile(
        name="jira",
        display_name="Jira",
        executable_names=["chrome", "chromium", "firefox", "brave", "edge"],
        window_title_patterns=["jira"],
        url_patterns=["atlassian.net", "jira"],
        focus_method="url",
        launch_command=None,
    ),
]


# =============================================================
#  PROFILE REGISTRY
# =============================================================

class ProfileRegistry:
    """Registry of app profiles for the Bridge Agent."""

    def __init__(self, profiles: Optional[List[AppProfile]] = None) -> None:
        self._profiles: dict[str, AppProfile] = {}
        for p in profiles or BUILTIN_PROFILES:
            self._profiles[p.name] = p

    def get(self, name: str) -> Optional[AppProfile]:
        """Get a profile by its short name."""
        return self._profiles.get(name)

    def list_names(self) -> List[str]:
        """List all registered profile names."""
        return list(self._profiles.keys())

    def detect_active_app(self, window_title: str) -> Optional[AppProfile]:
        """Detect which app profile matches the current window title."""
        for profile in self._profiles.values():
            if profile.match_window_title(window_title):
                return profile
        return None

    def register(self, profile: AppProfile) -> None:
        """Register a custom app profile."""
        self._profiles[profile.name] = profile


# Singleton registry
_default_registry: Optional[ProfileRegistry] = None


def get_registry() -> ProfileRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = ProfileRegistry()
    return _default_registry


# =============================================================
#  APP FOCUS / LAUNCH HELPERS
# =============================================================

def focus_app(profile: AppProfile) -> bool:
    """
    Focus or launch an application by its profile.

    Returns True if the app is now focused/launched.
    """
    try:
        # Try to find and focus existing window first
        from platforms.factory import get_window_mgmt
        wm = get_window_mgmt()

        # Attempt focus by window title pattern
        for pattern in profile.window_title_patterns:
            try:
                if wm.focus_window_by_title(pattern):
                    log.info("Focused %s by title pattern: %s", profile.name, pattern)
                    time.sleep(0.3)
                    return True
            except Exception:
                continue

        # If not found, try launching
        if profile.launch_command:
            log.info("Launching %s with: %s", profile.name, profile.launch_command)
            subprocess.Popen(profile.launch_command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2.0)  # Give the app time to open
            return True

        log.warning("Could not focus or launch %s", profile.name)
        return False

    except Exception as e:
        log.error("focus_app failed for %s: %s", profile.name, e)
        return False


def get_active_app_title() -> str:
    """Get the title of the currently focused window."""
    try:
        from platforms.factory import get_window_mgmt
        wm = get_window_mgmt()
        return wm.get_active_window_title() or ""
    except Exception as e:
        log.warning("Could not get active window title: %s", e)
        return ""
