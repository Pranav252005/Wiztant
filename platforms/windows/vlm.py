"""platforms/windows/vlm.py — Windows VLM / agent runtime implementing BaseVLM.

Wraps the Windows agent loop from the legacy core/vlm.py module.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from PIL import Image

from platforms.abstract import BaseVLM, BaseSystemAccess

log = logging.getLogger("platforms.windows.vlm")


class WindowsVLM(BaseVLM):
    """Windows VLM backend. Provides UIA + two-path agent loop."""

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
        return {"platform": "windows", "uia": True, "vision": True}

    def run_agent_loop(
        self,
        task: str,
        toast: Callable | None = None,
        progress_cb: Callable | None = None,
    ) -> str:
        """Execute agent task on Windows."""
        from platforms.windows._vlm_impl import run_agent_loop as _legacy_loop
        return _legacy_loop(task, toast=toast, progress_cb=progress_cb)
