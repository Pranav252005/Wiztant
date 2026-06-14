"""
core/agent_planner.py — Planner Brain (Qwen3-VL-235B) for the Three-Brain Agent.

Generates structured execution plans from user specifications + screenshots.
Supports initial planning and dynamic replanning.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from core.agent_engine import call_api, parse_json, to_base64
from core.agent_prompts import PLANNER_SYSTEM_PROMPT, format_planner_user_message
from core.agent_state import AgentPlan, Milestone

log = logging.getLogger("core.agent_planner")

# =============================================================
#  CONSTANTS
# =============================================================

PLANNER_MODEL = "qwen/qwen3-vl-235b-a22b-instruct"
PLANNER_TEMP = 0.3
PLANNER_MAX_TOKENS = 4096


# =============================================================
#  PLANNER BRAIN
# =============================================================

class PlannerBrain:
    """Generates structured plans from user specs using Qwen3-VL."""

    def __init__(
        self,
        model: str = PLANNER_MODEL,
        temperature: float = PLANNER_TEMP,
    ) -> None:
        self.model = model
        self.temperature = temperature

    def create_plan(
        self,
        user_spec: str,
        screenshot,
        history: List[Dict[str, Any]] | None = None,
    ) -> AgentPlan:
        """
        Create an initial plan from a user specification.

        Returns an AgentPlan with milestones, estimated steps, and detected tool.
        """
        try:
            b64 = to_base64(screenshot)
            messages = [
                {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": format_planner_user_message(user_spec, b64, history),
                },
            ]
            raw = call_api(self.model, messages, self.temperature, PLANNER_MAX_TOKENS)
            data = parse_json(raw)

            if data is None:
                log.warning("Planner returned non-JSON: %s", raw[:200])
                return self._fallback_plan(user_spec)

            return self._parse_plan(data)

        except Exception as e:
            log.error("Plan creation failed: %s", e)
            return self._fallback_plan(user_spec)

    def replan(
        self,
        original_plan: AgentPlan,
        new_spec: str,
        screenshot,
        execution_history: List[Dict[str, Any]],
        steps_remaining: float,
    ) -> AgentPlan:
        """
        Replan given new user requirements during a pause.

        Returns an updated AgentPlan that merges new requirements with
        locked completed steps.
        """
        completed = [m for m in original_plan.milestones if m.status == "completed"]
        pending = [m for m in original_plan.milestones if m.status != "completed"]

        history_text = "\n".join(
            f"  Step {h.get('step', '?')}: {h.get('action', '?')} — {h.get('status', '?')}"
            for h in execution_history[-10:]
        )

        prompt = (
            f"Original plan had {len(original_plan.milestones)} milestones.\n"
            f"Completed (LOCKED): {[m.title for m in completed]}\n"
            f"Pending: {[m.title for m in pending]}\n\n"
            f"New user request: {new_spec}\n\n"
            f"Execution history:\n{history_text}\n\n"
            f"Remaining step budget: {steps_remaining:.0f}\n\n"
            f"Generate an updated plan. Keep completed milestones locked. "
            f"Modify or insert new milestones for pending/completed affected steps. "
            f"Return JSON with the same schema as before."
        )

        try:
            b64 = to_base64(screenshot)
            messages = [
                {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                        },
                    ],
                },
            ]
            raw = call_api(self.model, messages, self.temperature, PLANNER_MAX_TOKENS)
            data = parse_json(raw)

            if data is None:
                log.warning("Replan returned non-JSON: %s", raw[:200])
                return original_plan

            return self._parse_plan(data)

        except Exception as e:
            log.error("Replan failed: %s", e)
            return original_plan

    def _parse_plan(self, data: Dict[str, Any]) -> AgentPlan:
        """Parse planner JSON output into an AgentPlan."""
        milestones: List[Milestone] = []
        for idx, m in enumerate(data.get("milestones", []), start=1):
            milestones.append(Milestone(
                step_id=m.get("step_id", idx),
                title=m.get("title", f"Step {idx}"),
                prompt=m.get("prompt", ""),
                expected_ide_actions=m.get("expected_ide_actions", 1),
                verification_cues=m.get("verification_cues", []),
                status=m.get("status", "pending"),
            ))

        return AgentPlan(
            plan_id=data.get("plan_id", str(uuid.uuid4())[:8]),
            detected_tool=data.get("detected_tool", "unknown"),
            tool_confidence=float(data.get("tool_confidence", 0.0)),
            estimated_steps=int(data.get("estimated_steps", len(milestones) * 5)),
            milestones=milestones,
        )

    def _fallback_plan(self, user_spec: str) -> AgentPlan:
        """Return a minimal fallback plan when the planner fails."""
        return AgentPlan(
            plan_id=str(uuid.uuid4())[:8],
            detected_tool="unknown",
            tool_confidence=0.0,
            estimated_steps=10,
            milestones=[
                Milestone(
                    step_id=1,
                    title="Execute user request",
                    prompt=user_spec,
                    expected_ide_actions=5,
                    verification_cues=["Task visibly completed"],
                ),
            ],
        )
