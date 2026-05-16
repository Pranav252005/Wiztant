"""
Lovable adapter — opens browser at lovable.dev, focuses prompt input,
clears it, and types the optimized prompt. Stops before submitting.
"""

from __future__ import annotations

import time
from typing import Any, Dict

from core.agent_v2.adapters.base import ToolAdapter


class LovableAdapter(ToolAdapter):
    name = "lovable"

    _URL = "https://lovable.dev"
    _BROWSER = "chrome"

    def is_available(self) -> bool:
        # Lovable is always "available" since we open it in the browser
        return True

    async def stage(self, action: Dict[str, Any]) -> Dict[str, Any]:
        prompt = action.get("value", "")
        if not prompt:
            return {"staged": False, "error": "empty prompt"}

        runtime = self._get_runtime()

        # 1. Open browser and navigate to Lovable
        try:
            runtime.open_browser(self._BROWSER, url=self._URL)
        except Exception as e:
            return {"staged": False, "error": f"Failed to open browser: {e}", "tool": "lovable"}

        time.sleep(3.0)  # Wait for page load

        # 2. Click on the prompt input area
        # Lovable's prompt input is typically centered near the top-middle of the page.
        # We use a heuristic click based on common screen sizes.
        w, h = runtime.screen_size()
        # Heuristic: prompt input is usually around (50%, 35-45% of screen)
        click_x = int(w * 0.5)
        click_y = int(h * 0.40)

        ok, msg = runtime.click(click_x, click_y)
        if not ok:
            return {"staged": False, "error": f"Could not click prompt field: {msg}", "tool": "lovable"}

        time.sleep(0.5)

        # 3. Clear any existing text
        runtime.clear_input_field()
        time.sleep(0.2)

        # 4. Type the prompt
        ok, msg = runtime.type_text(prompt, interval=0.005)
        if not ok:
            return {"staged": False, "error": f"Failed to type: {msg}", "tool": "lovable"}

        return {
            "staged": True,
            "tool": "lovable",
            "prompt": prompt,
            "note": "Prompt is staged in Lovable's input field. Review and press Enter to submit.",
            "auto_executed": False,
        }
