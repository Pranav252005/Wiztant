"""
core/agent_screenshots.py — Screenshot capture and window detection for the Three-Brain Agent.

Uses mss for cross-platform screen capture and delegates window title queries
to the platform runtime.
"""
from __future__ import annotations

import base64
import hashlib
import logging
from io import BytesIO
from typing import Optional, Tuple

from PIL import Image

try:
    import mss
except ImportError:
    mss = None  # type: ignore

log = logging.getLogger("core.agent_screenshots")

# =============================================================
#  SCREENSHOT CAPTURE
# =============================================================

class ScreenshotManager:
    """Manages screen capture with caching and resizing."""

    def __init__(self, max_width: int = 1280, quality: int = 82) -> None:
        self.max_width = max_width
        self.quality = quality
        self._last_hash: str = ""
        self._mss = mss.mss() if mss else None

    def capture(self, monitor_index: int | None = None) -> Image.Image:
        """Capture the full screen or a specific monitor."""
        if self._mss is None:
            raise RuntimeError("mss is not installed. Install with: pip install mss")

        try:
            if monitor_index is not None:
                mon = self._mss.monitors[monitor_index]
            else:
                mon = self._mss.monitors[0]  # 0 = all monitors combined
            raw = self._mss.grab(mon)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            return self._resize(img)
        except Exception as e:
            log.error("Screenshot capture failed: %s", e)
            # Return a blank image as fallback
            return Image.new("RGB", (1920, 1080), color=(0, 0, 0))

    def capture_active_window(self, runtime=None) -> Image.Image:
        """Capture the active/focused window area if possible, else full screen."""
        # Full-screen capture is more reliable cross-platform
        img = self.capture()
        # If runtime provides window bounds, we could crop here in the future
        return img

    def _resize(self, img: Image.Image) -> Image.Image:
        """Resize if wider than max_width, maintaining aspect ratio."""
        w, h = img.size
        if w > self.max_width:
            ratio = self.max_width / w
            new_size = (self.max_width, int(h * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        return img

    def to_base64(self, img: Image.Image) -> str:
        """Convert PIL Image to base64 JPEG string."""
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=self.quality)
        return base64.b64encode(buf.getvalue()).decode()

    def quick_hash(self, img: Image.Image) -> str:
        """Fast perceptual hash for loop detection."""
        try:
            thumb = img.resize((32, 32), Image.Resampling.LANCZOS).convert("L")
            return hashlib.md5(thumb.tobytes()).hexdigest()
        except Exception:
            return ""

    def has_changed(self, img: Image.Image) -> bool:
        """Check if the screenshot has changed since last call."""
        h = self.quick_hash(img)
        changed = h != self._last_hash
        self._last_hash = h
        return changed


# =============================================================
#  WINDOW DETECTION
# =============================================================

def get_active_window_title(runtime=None) -> str:
    """Return the title of the currently focused window."""
    if runtime is None:
        try:
            from platforms.factory import get_agent_runtime
            runtime = get_agent_runtime()
        except Exception as e:
            log.warning("Could not get runtime for window title: %s", e)
            return ""
    try:
        return runtime.get_foreground_app() or ""
    except Exception as e:
        log.warning("get_foreground_app failed: %s", e)
        return ""


def get_screen_size(runtime=None) -> Tuple[int, int]:
    """Return (width, height) of the primary display."""
    if runtime is None:
        try:
            from platforms.factory import get_agent_runtime
            runtime = get_agent_runtime()
        except Exception:
            return (1920, 1080)
    try:
        return runtime.screen_size()
    except Exception:
        return (1920, 1080)


def focus_window(title_substring: str, runtime=None) -> Tuple[bool, str]:
    """Find and focus a window by title substring."""
    if runtime is None:
        try:
            from platforms.factory import get_agent_runtime
            runtime = get_agent_runtime()
        except Exception as e:
            return False, f"No runtime: {e}"
    try:
        return runtime.focus_window_by_title(title_substring)
    except Exception as e:
        return False, str(e)
