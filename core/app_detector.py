"""
core/app_detector.py — Spec-driven app detection.

Loads app_config.json (generated from agent_rules spec files) and matches
any user request to the correct app to open. NEVER defaults to Arc.

Priority order:
  1. Explicit browser mention ("open Firefox" → firefox)
  2. Explicit system app mention ("registry", "theme" → settings/registry)
  3. Browser-task keywords with no browser named → default_browser (chrome)
  4. No match → None (caller decides)
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parent / "app_config.json"
_config: Optional[Dict[str, Any]] = None


# ── Config loading ────────────────────────────────────────────────────────────

def load_app_config() -> Dict[str, Any]:
    """Load and cache app_config.json. Returns config dict."""
    global _config
    if _config is not None:
        return _config
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            _config = json.load(f)
        logger.info(f"[AppDetector] Loaded app_config.json (v{_config.get('version', '?')})")
    except FileNotFoundError:
        logger.error(f"[AppDetector] app_config.json not found at {_CONFIG_PATH}")
        _config = {"browsers": {}, "system_apps": {}, "default_browser": "chrome",
                   "never_default_to": ["arc"], "browser_task_keywords": [],
                   "optimizations": {}}
    except json.JSONDecodeError as e:
        logger.error(f"[AppDetector] Failed to parse app_config.json: {e}")
        _config = {"browsers": {}, "system_apps": {}, "default_browser": "chrome",
                   "never_default_to": ["arc"], "browser_task_keywords": [],
                   "optimizations": {}}
    return _config


def reload_config() -> Dict[str, Any]:
    """Force reload config from disk."""
    global _config
    _config = None
    return load_app_config()


# ── Keyword helpers ───────────────────────────────────────────────────────────

def get_browser_keywords() -> Dict[str, List[str]]:
    """Return {browser_name: [keywords]} from config."""
    cfg = load_app_config()
    return {name: info.get("keywords", [])
            for name, info in cfg.get("browsers", {}).items()}


def get_system_task_keywords() -> Dict[str, List[str]]:
    """Return {app_name: [keywords]} for system apps from config."""
    cfg = load_app_config()
    return {name: info.get("keywords", [])
            for name, info in cfg.get("system_apps", {}).items()}


def get_all_keywords() -> Dict[str, List[str]]:
    """Return merged browser + system app keyword maps."""
    result = {}
    result.update(get_browser_keywords())
    result.update(get_system_task_keywords())
    return result


# ── Navigation & optimization helpers ────────────────────────────────────────

def get_navigation_pattern(app_name: str) -> Optional[Dict[str, Any]]:
    """Return the navigation spec dict for a given app name, or None."""
    cfg = load_app_config()
    app_name_lower = app_name.lower().strip()

    browsers = cfg.get("browsers", {})
    if app_name_lower in browsers:
        return browsers[app_name_lower].get("navigation")

    system_apps = cfg.get("system_apps", {})
    if app_name_lower in system_apps:
        return system_apps[app_name_lower].get("navigation")

    return None


def get_app_info(app_name: str) -> Optional[Dict[str, Any]]:
    """Return the full config entry for an app (path, process, keywords, etc.)."""
    cfg = load_app_config()
    app_name_lower = app_name.lower().strip()
    browsers = cfg.get("browsers", {})
    system_apps = cfg.get("system_apps", {})
    return browsers.get(app_name_lower) or system_apps.get(app_name_lower)


def get_optimization_rules(app_name: str) -> List[str]:
    """Return optimization hints for an app from config."""
    info = get_app_info(app_name)
    if info:
        return info.get("optimizations", [])
    cfg = load_app_config()
    return cfg.get("optimizations", {}).get("universal", {})


def get_launch_path(app_name: str) -> Optional[str]:
    """Return the executable path for an app, with %ENV% vars expanded."""
    info = get_app_info(app_name)
    if not info:
        return None
    path = info.get("path", "")
    return os.path.expandvars(path) if path else None


def get_window_title_hints(app_name: str) -> List[str]:
    """Return window title substrings that identify this app's window."""
    info = get_app_info(app_name)
    if not info:
        return [app_name]
    return info.get("window_title_contains", [app_name])


def get_default_browser() -> str:
    """Return the configured default browser name (never Arc)."""
    cfg = load_app_config()
    default = cfg.get("default_browser", "chrome")
    never = cfg.get("never_default_to", ["arc"])
    if default in never:
        # Safety: pick first browser that's not in the never list
        for name in cfg.get("browsers", {}):
            if name not in never:
                return name
        return "chrome"
    return default


# ── Core detection ────────────────────────────────────────────────────────────

def detect_app_from_request(user_request: str) -> Optional[str]:
    """
    Match a user request to the correct app using spec keywords.

    Priority:
      1. Explicit browser keyword match → return that browser
      2. Explicit system app keyword match → return that system app
      3. Browser-task keyword present but no browser named → default_browser
      4. No match → None

    CRITICAL: Arc is NEVER returned unless "arc" is explicitly in the request.
    """
    cfg = load_app_config()
    request_lower = user_request.lower()
    never_default_to = {n.lower() for n in cfg.get("never_default_to", ["arc"])}

    # ── Priority 1: Explicit browser match ───────────────────────────────────
    browsers = cfg.get("browsers", {})
    for browser_name, browser_info in browsers.items():
        if browser_info.get("never_open_unless_requested") and browser_name in never_default_to:
            # Only match Arc if it's explicitly in the request
            if not _keyword_in_request(["arc browser", "arc"], request_lower):
                continue
        for keyword in browser_info.get("keywords", []):
            if _keyword_in_request([keyword], request_lower):
                logger.info(
                    f"[AppDetector] Browser match: '{browser_name}' "
                    f"(keyword='{keyword}', source=browser_navigation_spec.md)"
                )
                return browser_name

    # ── Priority 2: Explicit system app match ────────────────────────────────
    system_apps = cfg.get("system_apps", {})
    for app_name, app_info in system_apps.items():
        for keyword in app_info.get("keywords", []):
            if _keyword_in_request([keyword], request_lower):
                logger.info(
                    f"[AppDetector] System app match: '{app_name}' "
                    f"(keyword='{keyword}', source=agent_navigation.md)"
                )
                return app_name

    # ── Priority 3: Generic browser task → use default browser ───────────────
    browser_task_keywords = cfg.get("browser_task_keywords", [])
    if _keyword_in_request(browser_task_keywords, request_lower):
        default = get_default_browser()
        logger.info(
            f"[AppDetector] Browser task detected, no browser specified → "
            f"default_browser='{default}' (never Arc)"
        )
        return default

    logger.info(f"[AppDetector] No app match for: '{user_request[:80]}'")
    return None


def is_browser(app_name: str) -> bool:
    """Return True if app_name is a browser in config."""
    cfg = load_app_config()
    return app_name.lower() in cfg.get("browsers", {})


def is_system_app(app_name: str) -> bool:
    """Return True if app_name is a system app in config."""
    cfg = load_app_config()
    return app_name.lower() in cfg.get("system_apps", {})


def build_nav_context_for_prompt(app_name: str, task: str) -> str:
    """
    Build a concise navigation context string to inject into the agent prompt.
    Tells the agent which app it should be in and how to navigate it.
    """
    nav = get_navigation_pattern(app_name)
    info = get_app_info(app_name)
    if not nav or not info:
        return ""

    lines = [
        f"ACTIVE APP: {app_name.upper()}",
        f"Task: {task}",
    ]

    # Address bar shortcut
    addr = nav.get("focus_address_bar") or nav.get("action_sequence_open", [None])[0]
    if addr:
        lines.append(f"Focus address bar / open: {addr}")

    # Action sequence for navigation
    seq_key = "action_sequence_navigate" if is_browser(app_name) else "action_sequence_open"
    seq = nav.get(seq_key, [])
    if seq:
        lines.append("Navigation steps:")
        for step in seq:
            lines.append(f"  {step}")

    # Key shortcuts
    shortcuts = nav.get("shortcuts", {})
    if shortcuts:
        lines.append("Key shortcuts:")
        for action, shortcut in list(shortcuts.items())[:6]:
            lines.append(f"  {action}: {shortcut}")

    # UI element descriptions
    ui_desc = nav.get("ui_descriptions", {})
    if ui_desc:
        lines.append("UI element descriptions for grounding:")
        for elem, desc in list(ui_desc.items())[:4]:
            lines.append(f'  {elem}: "{desc}"')

    # Optimizations
    opts = get_optimization_rules(app_name)
    if opts:
        lines.append(f"Optimizations: {', '.join(opts[:4])}")

    return "\n".join(lines)


# ── Private helpers ───────────────────────────────────────────────────────────

def _keyword_in_request(keywords: List[str], request_lower: str) -> bool:
    """Match keywords against request using word boundaries for short words."""
    for kw in keywords:
        kw_lower = kw.lower()
        # Use word-boundary regex for short keywords (≤5 chars) to avoid
        # substring false-positives like "arc" inside "search".
        if len(kw_lower) <= 5:
            if re.search(r'\b' + re.escape(kw_lower) + r'\b', request_lower):
                return True
        else:
            if kw_lower in request_lower:
                return True
    return False
