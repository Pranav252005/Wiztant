"""platforms/linux/vlm.py — Linux VLM / agent runtime implementing BaseVLM.

Wraps the Linux agent loop from the legacy core/vlm_linux.py module.
All platform-specific action execution is routed through BaseSystemAccess.
"""
from __future__ import annotations

import io
import logging
import os
import subprocess
from typing import Any, Callable, Optional

from PIL import Image

from platforms.abstract import BaseVLM, BaseSystemAccess

log = logging.getLogger("platforms.linux.vlm")


class LinuxVLM(BaseVLM):
    """Linux VLM backend. Provides screenshot capture and delegates agent loop."""

    def __init__(self, system_access: BaseSystemAccess | None = None):
        self._system = system_access

    def _get_system(self) -> BaseSystemAccess:
        if self._system is None:
            from platforms.factory import get_system_access
            self._system = get_system_access()
        return self._system

    # ── BaseVLM interface ───────────────────────────────────────────────────────

    def capture(self) -> Image.Image:
        return self._get_system().take_screenshot()

    def analyze(self, prompt: str, image: Image.Image) -> dict:
        """Analyze image with vision model. Not used directly — agent loop handles this."""
        return {}

    def get_capabilities(self) -> dict:
        return {"platform": "linux", "uia": False, "vision": True}

    def run_agent_loop(
        self,
        task: str,
        toast: Callable | None = None,
        progress_cb: Callable | None = None,
    ) -> str:
        """Execute agent task on Linux."""
        from platforms.linux._vlm_impl import run_agent_loop as _legacy_loop
        return _legacy_loop(task, toast=toast, progress_cb=progress_cb)

    # ── Legacy helpers ──────────────────────────────────────────────────────────

    def capture_screenshot_to_bytes(self) -> bytes:
        """Capture full screen and return raw PNG bytes."""
        import os
        if not os.getenv("DISPLAY") and not os.getenv("WAYLAND_DISPLAY"):
            raise RuntimeError(
                "No display detected (DISPLAY/WAYLAND_DISPLAY not set). "
                "Screenshot requires a running desktop session."
            )
        try:
            from mss import mss
            from PIL import Image
            with mss() as sct:
                monitor = sct.monitors[0]
                img = sct.grab(monitor)
                pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
            buf = io.BytesIO()
            pil_img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception:
            pass
        try:
            result = subprocess.run(["scrot", "-"], capture_output=True, timeout=5)
            if result.returncode == 0 and result.stdout:
                return result.stdout
        except FileNotFoundError:
            pass
        raise RuntimeError("Screenshot failed. Ensure you have an active desktop session.")
