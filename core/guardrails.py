"""
core/guardrails.py — Agent safety guardrails.

Provides pre-execution checks: destructive action detection, coordinate
validation, and loop detection. Designed to be called inside vlm._phase2_loop().
"""

import re
import hashlib
from typing import Optional

# Screen bounds (conservative — agent should not click near edges)
SCREEN_MIN_X = 5
SCREEN_MIN_Y = 5
SCREEN_MAX_X = 3840  # supports up to 4K
SCREEN_MAX_Y = 2160

# Actions that require extra scrutiny before execution.
# These are patterns that, combined with the action context, signal risk.
DESTRUCTIVE_KEYWORDS = [
    r"\bdelete\b.*\bfile\b",
    r"\bremove\b.*\bfile\b",
    r"\bformat\b.*\b(drive|disk|partition|volume)\b",
    r"\b(rm|del)\b.*(-rf?|/s|/q)\b",
    r"\bdrop\b.*\b(table|database|db)\b",
    r"\btruncate\b.*\btable\b",
    r"\buninstall\b.*\b(program|app|software)\b",
    r"\berase\b.*\b(disk|drive|partition)\b",
    r"\bwipe\b.*\b(disk|drive|partition|data)\b",
    r"\bshutdown\b",
    r"\brestart\b.*\b(computer|system|pc)\b",
    r"\bterminate\b.*\bprocess\b",
    r"\bkill\b.*\bprocess\b",
    r"\bempty\b.*\b(recycle|trash)\b",
]

_COMPILED_DESTRUCTIVE = [re.compile(p, re.IGNORECASE) for p in DESTRUCTIVE_KEYWORDS]


def is_destructive_action(action_text: str) -> tuple[bool, str]:
    """
    Returns (is_destructive, matched_reason).
    Uses keyword/regex blocklist only — no LLM call here.
    """
    for pattern in _COMPILED_DESTRUCTIVE:
        m = pattern.search(action_text)
        if m:
            return True, f"destructive_keyword:{m.group(0)}"
    return False, ""


def validate_coordinates(x: int, y: int, screen_w: int = 1920, screen_h: int = 1080) -> tuple[bool, str]:
    """Returns (valid, reason). Rejects clicks near screen edges or outside bounds."""
    try:
        xv = int(x)
        yv = int(y)
    except (TypeError, ValueError):
        return False, f"coord_invalid_type:({type(x).__name__},{type(y).__name__})"
    if xv < SCREEN_MIN_X or yv < SCREEN_MIN_Y:
        return False, f"coord_too_low:({xv},{yv})"
    if xv >= screen_w - SCREEN_MIN_X or yv >= screen_h - SCREEN_MIN_Y:
        return False, f"coord_out_of_bounds:({xv},{yv}) screen=({screen_w},{screen_h})"
    return True, ""


def detect_loop(history: list[tuple[str, str]], window: int = 3) -> bool:
    """
    Returns True if the last `window` (action, screenshot_hash) pairs are identical —
    indicating the agent is stuck in a no-progress loop.
    """
    if len(history) < window:
        return False
    last = history[-window:]
    return len(set(last)) == 1


def screenshot_hash(pixel_data: bytes) -> str:
    """Quick perceptual hash (MD5) of raw screenshot bytes for loop detection."""
    return hashlib.md5(pixel_data).hexdigest()


def pixel_diff_score(before: bytes, after: bytes) -> float:
    """
    Rough pixel-change ratio between two raw screenshot byte strings.
    Returns 0.0 (identical) to 1.0 (completely different).
    """
    if len(before) != len(after) or len(before) == 0:
        return 1.0
    diff = sum(1 for a, b in zip(before, after) if a != b)
    return diff / len(before)
