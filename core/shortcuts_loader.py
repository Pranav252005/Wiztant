"""
Shortcuts loader for agent planner.
Loads data/shortcuts_map.json and formats shortcut hints per task category.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger("core.shortcuts_loader")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SHORTCUTS_PATH = _PROJECT_ROOT / "data" / "shortcuts_map.json"


def _load_map() -> dict:
    try:
        with _SHORTCUTS_PATH.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        log.warning("Failed to load shortcuts map: %s", exc)
        return {}


_MAP = _load_map()


def load_shortcuts(category: Optional[str]) -> str:
    """Return a formatted string of shortcuts for *category*, including globals."""
    if not _MAP:
        return ""

    cat = (category or "").upper()
    parts: list[str] = []

    # Global shortcuts first
    global_data = _MAP.get("global")
    if global_data and isinstance(global_data, dict):
        shortcuts = global_data.get("shortcuts", [])
        if shortcuts:
            parts.append("[Global]")
            for entry in shortcuts:
                keys = entry.get("keys", "")
                action = entry.get("action", "")
                if keys and action:
                    parts.append(f"  {keys}: {action}")

    # Category-specific shortcuts
    cat_data = _MAP.get(cat)
    if cat_data and isinstance(cat_data, dict):
        name = cat_data.get("name", cat)
        primary_apps = cat_data.get("primary_apps", [])
        if primary_apps:
            parts.append(f"\n[{name} — Primary apps: {', '.join(primary_apps)}]")
        else:
            parts.append(f"\n[{name}]")

        shortcuts = cat_data.get("shortcuts", [])
        if shortcuts:
            for entry in shortcuts:
                keys = entry.get("keys", "")
                action = entry.get("action", "")
                if keys and action:
                    parts.append(f"  {keys}: {action}")

        sequences = cat_data.get("sequences", [])
        if sequences:
            parts.append("\nSequences:")
            for entry in sequences:
                goal = entry.get("goal", "")
                steps = entry.get("steps", [])
                if goal and steps:
                    parts.append(f"  {goal}: {' -> '.join(steps)}")

        fallbacks = cat_data.get("fallbacks", [])
        if fallbacks:
            parts.append("\nFallbacks:")
            for entry in fallbacks:
                condition = entry.get("if", "")
                steps = entry.get("try", [])
                if condition and steps:
                    parts.append(f"  If {condition}: {' -> '.join(steps)}")

    return "\n".join(parts)
