"""
shortcuts_loader — compact shortcut-map injection for Qwen's planning prompt.

Reads `data/shortcuts_map.json` once per process (module-level cache) and returns a
plain-text summary for a given agent task category (A-F) plus the shared 'global'
section. Output is budgeted to stay under ~400 tokens so it can be appended to the
planner system prompt without crowding the context.

Public API:
    load_shortcuts(category: str) -> str
    get_all_shortcuts() -> dict
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Paths & cache ─────────────────────────────────────────────────────────────

_MODULE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _MODULE_DIR.parent
_SHORTCUTS_PATH = _PROJECT_ROOT / "data" / "shortcuts_map.json"

_CACHE: Optional[Dict[str, Any]] = None

# Soft budget — ~4 chars/token → 400 tokens ≈ 1600 chars.
_MAX_CHARS_PER_CATEGORY = 1600


def _load_from_disk() -> Dict[str, Any]:
    """Read and parse shortcuts_map.json. Returns {} on any error."""
    try:
        with open(_SHORTCUTS_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def get_all_shortcuts() -> Dict[str, Any]:
    """Return the full parsed shortcuts map. Cached; safe to call often."""
    global _CACHE
    if _CACHE is None:
        _CACHE = _load_from_disk()
    return _CACHE


# ── Formatting helpers ────────────────────────────────────────────────────────

def _fmt_shortcut_list(items: List[Dict[str, Any]], limit: int = 40) -> List[str]:
    lines: List[str] = []
    for entry in items[:limit]:
        keys = entry.get("keys", "").strip()
        action = entry.get("action", "").strip()
        if keys and action:
            lines.append(f"  - {keys} -> {action}")
    return lines


def _fmt_sequence_list(items: List[Dict[str, Any]], limit: int = 10) -> List[str]:
    lines: List[str] = []
    for entry in items[:limit]:
        goal = entry.get("goal", "").strip()
        steps = entry.get("steps", [])
        if not goal or not isinstance(steps, list) or not steps:
            continue
        step_str = " -> ".join(str(s) for s in steps)
        lines.append(f"  - {goal}: {step_str}")
    return lines


def _fmt_fallback_list(items: List[Dict[str, Any]], limit: int = 6) -> List[str]:
    lines: List[str] = []
    for entry in items[:limit]:
        cond = entry.get("if", "").strip()
        remedy = entry.get("try", [])
        if not cond:
            continue
        if isinstance(remedy, list):
            remedy_str = " -> ".join(str(s) for s in remedy)
        else:
            remedy_str = str(remedy)
        lines.append(f"  - if {cond}: {remedy_str}")
    return lines


def _fmt_run_commands(items: List[Dict[str, Any]], limit: int = 10) -> List[str]:
    lines: List[str] = []
    for entry in items[:limit]:
        cmd = entry.get("cmd", "").strip()
        opens = entry.get("opens", "").strip()
        if cmd and opens:
            lines.append(f"  - {cmd} -> {opens}")
    return lines


def _render_category_block(cat_key: str, cat_data: Dict[str, Any]) -> str:
    name = cat_data.get("name", cat_key)
    apps = cat_data.get("primary_apps", [])
    header = f"[Category {cat_key} - {name}]"
    if apps:
        header += f" (apps: {', '.join(apps)})"
    parts: List[str] = [header]

    # Merge outlook_shortcuts + slack_shortcuts under Shortcuts when present
    shortcuts = list(cat_data.get("shortcuts", []) or [])
    outlook_sc = cat_data.get("outlook_shortcuts", []) or []
    slack_sc = cat_data.get("slack_shortcuts", []) or []

    if shortcuts:
        parts.append("Shortcuts:")
        parts.extend(_fmt_shortcut_list(shortcuts))
    if outlook_sc:
        parts.append("Outlook shortcuts:")
        parts.extend(_fmt_shortcut_list(outlook_sc))
    if slack_sc:
        parts.append("Slack shortcuts:")
        parts.extend(_fmt_shortcut_list(slack_sc))

    sequences = cat_data.get("sequences", []) or []
    if sequences:
        parts.append("Sequences:")
        parts.extend(_fmt_sequence_list(sequences))

    run_cmds = cat_data.get("run_commands", []) or []
    if run_cmds:
        parts.append("Run-dialog commands:")
        parts.extend(_fmt_run_commands(run_cmds))

    fallbacks = cat_data.get("fallbacks", []) or []
    if fallbacks:
        parts.append("Fallbacks:")
        parts.extend(_fmt_fallback_list(fallbacks))

    return "\n".join(parts)


def _render_global_block(global_data: Dict[str, Any]) -> str:
    shortcuts = global_data.get("shortcuts", []) or []
    if not shortcuts:
        return ""
    parts: List[str] = ["[Global - universal Windows shortcuts]"]
    parts.extend(_fmt_shortcut_list(shortcuts, limit=15))
    return "\n".join(parts)


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    # Trim at a newline boundary when possible.
    cut = text.rfind("\n", 0, max_chars)
    if cut < max_chars - 200:
        cut = max_chars
    return text[:cut].rstrip() + "\n  ... (truncated)"


# ── Public API ────────────────────────────────────────────────────────────────

def load_shortcuts(category: str) -> str:
    """
    Return a compact plain-text summary of shortcuts for the given category,
    formatted for injection into Qwen's planning prompt. Always includes the
    shared 'global' section after the category block.

    Unknown or missing category -> empty string (no crash).
    """
    if not category:
        return ""
    data = get_all_shortcuts()
    if not data:
        return ""

    cat_key = str(category).strip().upper()
    cat_data = data.get(cat_key)
    if not isinstance(cat_data, dict):
        return ""

    blocks: List[str] = []
    cat_block = _render_category_block(cat_key, cat_data)
    if cat_block:
        blocks.append(cat_block)

    global_data = data.get("global")
    if isinstance(global_data, dict):
        gblock = _render_global_block(global_data)
        if gblock:
            blocks.append(gblock)

    text = "\n\n".join(blocks)
    return _truncate(text, _MAX_CHARS_PER_CATEGORY)


def reload_shortcuts() -> Dict[str, Any]:
    """Force re-read from disk. Useful during development."""
    global _CACHE
    _CACHE = None
    return get_all_shortcuts()


__all__ = ["load_shortcuts", "get_all_shortcuts", "reload_shortcuts"]
