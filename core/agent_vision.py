"""
core/agent_vision.py — Vision Brain (Gemini 3 Flash) for the Three-Brain Agent.

Continuously monitors the IDE state: tool detection, element localization,
error detection, and completion signals.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from core.agent_engine import call_api, parse_json, to_base64
from core.agent_prompts import (
    VISION_SYSTEM_PROMPT,
    format_vision_user_message,
    format_verify_change_message,
)

log = logging.getLogger("core.agent_vision")

# =============================================================
#  CONSTANTS
# =============================================================

VISION_MODEL = "google/gemini-3-flash-preview"
VISION_TEMP = 0.1
VISION_MAX_TOKENS = 1024


# =============================================================
#  VISION BRAIN
# =============================================================

class VisionBrain:
    """Analyzes screenshots using Gemini Flash for IDE state detection."""

    def __init__(self, model: str = VISION_MODEL, temperature: float = VISION_TEMP) -> None:
        self.model = model
        self.temperature = temperature
        self._last_result: Optional[Dict[str, Any]] = None

    def analyze(
        self,
        screenshot,
        question: str | None = None,
    ) -> Dict[str, Any]:
        """
        Analyze a screenshot and return structured IDE state.

        Returns dict with keys:
          tool_detected, tool_confidence, window_state, is_loading,
          is_generating, last_message_status, visible_elements,
          detected_errors, suggested_next_action
        """
        try:
            b64 = to_base64(screenshot)
            messages = [
                {"role": "system", "content": VISION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": format_vision_user_message(b64, question),
                },
            ]
            raw = call_api(self.model, messages, self.temperature, VISION_MAX_TOKENS)
            result = parse_json(raw)

            if result is None:
                log.warning("Vision model returned non-JSON: %s", raw[:200])
                result = self._fallback_result()

            result = self._normalize_result(result)
            self._last_result = result
            return result

        except Exception as e:
            log.error("Vision analysis failed: %s", e)
            return self._fallback_result()

    def verify_change(
        self,
        before_screenshot,
        after_screenshot,
        expected_action: str,
    ) -> Dict[str, Any]:
        """Compare before/after screenshots to verify an action had effect."""
        try:
            before_b64 = to_base64(before_screenshot)
            after_b64 = to_base64(after_screenshot)
            messages = [
                {
                    "role": "user",
                    "content": format_verify_change_message(before_b64, after_b64, expected_action),
                },
            ]
            raw = call_api(self.model, messages, self.temperature, VISION_MAX_TOKENS)
            result = parse_json(raw)

            if result is None:
                log.warning("Verify-change returned non-JSON: %s", raw[:200])
                return {"changed": False, "description": "parse failed", "completion_detected": False}

            return {
                "changed": bool(result.get("changed", False)),
                "description": result.get("description", ""),
                "completion_detected": bool(result.get("completion_detected", False)),
            }

        except Exception as e:
            log.error("Verify change failed: %s", e)
            return {"changed": False, "description": str(e), "completion_detected": False}

    def detects_completion(self) -> bool:
        """Check if the last analysis indicated completion."""
        if self._last_result is None:
            return False
        status = self._last_result.get("last_message_status", "").lower()
        return status in ("completed", "done", "finished")

    def detects_error(self) -> bool:
        """Check if the last analysis detected an error state."""
        if self._last_result is None:
            return False
        errors = self._last_result.get("detected_errors", [])
        return bool(errors)

    def get_element_location(self, element_name: str) -> Optional[tuple[float, float]]:
        """Get normalized coordinates of a named element from last analysis."""
        if self._last_result is None:
            return None
        elements = self._last_result.get("visible_elements", {})
        elem = elements.get(element_name)
        if elem and isinstance(elem, dict):
            x = elem.get("x_norm")
            y = elem.get("y_norm")
            if x is not None and y is not None:
                return float(x), float(y)
        return None

    def _normalize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure all expected keys exist with sensible defaults."""
        defaults = {
            "tool_detected": "unknown",
            "tool_confidence": 0.0,
            "window_state": "unknown",
            "is_loading": False,
            "is_generating": False,
            "last_message_status": "idle",
            "visible_elements": {},
            "detected_errors": [],
            "suggested_next_action": "wait",
        }
        normalized = {**defaults, **result}
        # Ensure visible_elements is a dict
        if not isinstance(normalized["visible_elements"], dict):
            normalized["visible_elements"] = {}
        # Ensure detected_errors is a list
        if not isinstance(normalized["detected_errors"], list):
            normalized["detected_errors"] = []
        return normalized

    def _fallback_result(self) -> Dict[str, Any]:
        return {
            "tool_detected": "unknown",
            "tool_confidence": 0.0,
            "window_state": "unknown",
            "is_loading": False,
            "is_generating": False,
            "last_message_status": "idle",
            "visible_elements": {},
            "detected_errors": [],
            "suggested_next_action": "wait",
        }
