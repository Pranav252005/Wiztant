"""core/platform_backends.py — DEPRECATED shim. Delegates to platforms.factory.

This module is kept temporarily for backward compatibility while consumers migrate
to importing from platforms.factory directly. Do not add new code here.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

log = logging.getLogger("core.platform_backends")

# Lazy singletons — instantiated on first use so importing this module
# on either OS never crashes due to missing platform-specific deps.
_system = None
_window = None


def _sys():
    global _system
    if _system is None:
        from platforms.factory import get_system_access
        _system = get_system_access()
    return _system


def _win():
    global _window
    if _window is None:
        from platforms.factory import get_window_mgmt
        _window = get_window_mgmt()
    return _window


# ═══════════════════════════════════════════════════════════════════════════════
# Screenshot (cross-platform via mss)
# ═══════════════════════════════════════════════════════════════════════════════

def screenshot() -> Image.Image:
    return _sys().take_screenshot()


def screenshot_to_bytes(fmt: str = "PNG") -> bytes:
    img = screenshot()
    from io import BytesIO
    buf = BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════════
# Display info
# ═══════════════════════════════════════════════════════════════════════════════

def list_monitors() -> List[dict]:
    return _sys().list_monitors()


def screen_size() -> Tuple[int, int]:
    return _sys().screen_size()


def cursor_position() -> Tuple[int, int]:
    return _sys().cursor_position()


# ═══════════════════════════════════════════════════════════════════════════════
# Coordinate helpers (cross-platform, pure Python)
# ═══════════════════════════════════════════════════════════════════════════════

def translate_coordinates(x_1000: Any, y_1000: Any, reason: str = "") -> Optional[Tuple[int, int]]:
    try:
        xv = int(float(x_1000))
        yv = int(float(y_1000))
    except (TypeError, ValueError):
        log.warning("Invalid coordinates %s: x=%r y=%r", reason, x_1000, y_1000)
        return None
    if not (0 <= xv <= 1000 and 0 <= yv <= 1000):
        log.warning("Out of range coordinates %s: x=%d y=%d", reason, xv, yv)
        return None
    w, h = screen_size()
    return int(xv / 1000 * w), int(yv / 1000 * h)


def validate_screen_coordinates(x: Any, y: Any, reason: str = "") -> Optional[Tuple[int, int]]:
    try:
        xv = int(float(x))
        yv = int(float(y))
    except (TypeError, ValueError):
        log.warning("Invalid screen coords %s: x=%r y=%r", reason, x, y)
        return None
    if not (-1000 <= xv <= 10000 and -1000 <= yv <= 10000):
        log.warning("Suspicious screen coords %s: x=%d y=%d", reason, xv, yv)
        return None
    return xv, yv


# ═══════════════════════════════════════════════════════════════════════════════
# Mouse / Keyboard
# ═══════════════════════════════════════════════════════════════════════════════

def click(x: int, y: int, button: str = "left", clicks: int = 1) -> Tuple[bool, str]:
    return _sys().click(x, y, button=button, clicks=clicks)


def move(x: int, y: int) -> Tuple[bool, str]:
    return _sys().move(x, y)


def scroll(x: int, y: int, amount: int) -> Tuple[bool, str]:
    return _sys().scroll(x, y, amount)


def type_text(text: str, interval: float = 0.01) -> Tuple[bool, str]:
    return _sys().type_text(text, interval=interval)


def press_key(key: str) -> Tuple[bool, str]:
    return _sys().press_key(key)


def hotkey(*keys: str) -> Tuple[bool, str]:
    return _sys().hotkey(*keys)


# ═══════════════════════════════════════════════════════════════════════════════
# App / Window management
# ═══════════════════════════════════════════════════════════════════════════════

def launch_app(app_name: str) -> str:
    return _sys().launch_app(app_name)


def launch_browser(name: str, url: Optional[str] = None, profile: Optional[str] = None) -> str:
    return _sys().launch_browser(name, url=url, profile=profile)


def ensure_app_open(app_name: str, url: Optional[str] = None, profile: Optional[str] = None) -> str:
    return _sys().ensure_app_open(app_name, url=url, profile=profile)


def get_foreground_app() -> str:
    return _sys().get_foreground_app()


def list_windows() -> List[Tuple[str, Any]]:
    return _win().list_windows()


def raise_window(window_id: Any) -> bool:
    return _sys().raise_window(window_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Platform helpers
# ═══════════════════════════════════════════════════════════════════════════════

import sys


def platform_name() -> str:
    return "windows" if sys.platform == "win32" else "linux"


def modifier_key() -> str:
    return "win" if sys.platform == "win32" else "super"


# ═══════════════════════════════════════════════════════════════════════════════
# OCR (best-effort cross-platform)
# ═══════════════════════════════════════════════════════════════════════════════

import os

try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = os.getenv(
        "TESSERACT_PATH",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe" if sys.platform == "win32" else "tesseract"
    )
    TESSERACT_OK = True
except ImportError:
    TESSERACT_OK = False
    pytesseract = None


def ocr_image(img: Image.Image) -> str:
    if not TESSERACT_OK:
        return ""
    try:
        return pytesseract.image_to_string(img) or ""
    except Exception as e:
        log.warning("OCR failed: %s", e)
        return ""
