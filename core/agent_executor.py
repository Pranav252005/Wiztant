"""
core/agent_executor.py — Executor Brain (UI-TARS 1.5-7B) for the Three-Brain Agent.

Given a screenshot and task instruction, predicts the next GUI action(s).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core.agent_engine import call_api, to_base64
from core.agent_prompts import EXECUTOR_SYSTEM_PROMPT, format_executor_user_message
from core.agent_actions import AgentAction, parse_ui_tars_output, count_step_cost

log = logging.getLogger("core.agent_executor")

# =============================================================
#  CONSTANTS
# =============================================================

EXECUTOR_MODEL = "bytedance/ui-tars-1.5-7b"
EXECUTOR_TEMP = 0.2
EXECUTOR_MAX_TOKENS = 512


# =============================================================
#  EXECUTOR BRAIN
# =============================================================

class ExecutorBrain:
    """Predicts GUI actions using UI-TARS."""

    def __init__(
        self,
        model: str = EXECUTOR_MODEL,
        temperature: float = EXECUTOR_TEMP,
    ) -> None:
        self.model = model
        self.temperature = temperature

    def predict(
        self,
        screenshot,
        task: str,
        hints: Dict[str, Any] | None = None,
        history: List[str] | None = None,
    ) -> List[AgentAction]:
        """
        Predict the next action(s) given a screenshot and task.

        Returns a list of parsed AgentAction objects.
        """
        try:
            b64 = to_base64(screenshot)
            messages = [
                {"role": "system", "content": EXECUTOR_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": format_executor_user_message(b64, task, hints, history),
                },
            ]
            raw = call_api(self.model, messages, self.temperature, EXECUTOR_MAX_TOKENS)

            if not raw:
                log.error("Executor returned empty response")
                return [WaitAction(seconds=2.0)]

            # Get screen size for coordinate normalization (UI-TARS may return absolute pixels)
            try:
                from platforms.factory import get_agent_runtime
                rt = get_agent_runtime()
                screen_w, screen_h = rt.screen_size()
            except Exception:
                screen_w, screen_h = 1920, 1080

            actions = parse_ui_tars_output(raw, screen_w=screen_w, screen_h=screen_h)
            if not actions:
                log.warning("Executor returned unparseable output: %s", raw[:200])
                return [WaitAction(seconds=2.0)]

            log.info("Executor predicted %d action(s), cost=%.1f", len(actions), count_step_cost(actions))
            return actions

        except Exception as e:
            log.error("Executor prediction failed: %s", e)
            return [WaitAction(seconds=2.0)]

    def predict_with_retry(
        self,
        screenshot,
        task: str,
        hints: Dict[str, Any] | None = None,
        history: List[str] | None = None,
        max_retries: int = 2,
    ) -> List[AgentAction]:
        """Predict with retry on failure."""
        for attempt in range(max_retries + 1):
            actions = self.predict(screenshot, task, hints, history)
            if actions and not all(isinstance(a, WaitAction) for a in actions):
                return actions
            log.warning("Executor retry %d/%d", attempt + 1, max_retries)
        return [WaitAction(seconds=2.0)]


# Re-export for convenience
from core.agent_actions import (  # noqa: E402
    ClickAction,
    DoubleClickAction,
    TypeAction,
    PressAction,
    ScrollAction,
    WaitAction,
    DragAction,
)
