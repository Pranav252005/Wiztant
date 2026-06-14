"""core/workflow_planner.py — Natural language intent → WorkflowPlan.

Uses an LLM (OpenRouter) to convert free-form user intent into a structured
WorkflowPlan. Any disallowed actions suggested by the LLM are replaced with
ask_human gates.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from core.agent_engine import call_api, PLANNER_MODEL, TEMP_PLAN, PLAN_MAX_TOKENS
from core.workflow_runtime import WorkflowPlan, WorkflowStep, ALLOWED_ACTIONS

log = logging.getLogger("core.workflow_planner")


_PLANNER_SYSTEM_PROMPT = """You are a Workflow Planner. Convert the user's intent into a structured WorkflowPlan.

You may ONLY use these actions: open_app, focus_window, navigate_to, click, type, scroll, hotkey, copy, paste, screenshot, wait, read_screen, ask_human, return_result.
You may NEVER: create files, edit files, delete files, run shell commands, use git, write code, install packages.
The workflow should minimize steps. Combine multiple keystrokes into hotkey where possible.
If the user intent is vague or ambiguous, plan a minimal safe version and use ask_human for clarification.

Output valid JSON matching this exact schema:
{
  "intent": "short description",
  "apps_required": ["browser", "slack"],
  "steps": [
    {"id": "1", "app": "browser", "action": "open_app", "description": "...", "params": {}, "verification": null, "requires_decision": false}
  ],
  "estimated_budget": 10,
  "result_type": "summary"
}

result_type must be one of: summary, link, clipboard, notification.
"""


class WorkflowPlanner:
    """Converts natural language intent into a structured WorkflowPlan."""

    def plan(self, intent: str) -> WorkflowPlan:
        """Generate a WorkflowPlan from a user intent string."""
        system_prompt = _PLANNER_SYSTEM_PROMPT
        # Tell the planner which apps the user has authorized so it knows it can
        # log into them automatically (no secrets are included — see
        # core/integrations.agent_context_block).
        try:
            from core.integrations import agent_context_block
            ctx = agent_context_block()
            if ctx:
                system_prompt = f"{_PLANNER_SYSTEM_PROMPT}\n\n{ctx}"
        except Exception:
            pass

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Create a workflow plan for: {intent}"},
        ]

        try:
            raw = call_api(
                model=PLANNER_MODEL,
                messages=messages,
                temperature=TEMP_PLAN,
                max_tokens=PLAN_MAX_TOKENS,
            )
        except Exception as e:
            log.error("Planner API call failed: %s", e)
            return self._fallback_plan(intent, f"API error: {e}")

        parsed = self._parse_json(raw)
        if parsed is None:
            log.warning("Planner returned unparseable JSON, using fallback")
            return self._fallback_plan(intent, "Unparseable planner response")

        return self._build_plan(intent, parsed)

    # ── Internal helpers ───────────────────────────────────────────────────

    def _parse_json(self, text: str) -> Dict[str, Any] | None:
        """Extract and parse JSON from an LLM response."""
        if not text:
            return None
        text = text.strip()
        # Remove markdown fences
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find the first JSON object
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass
            return None

    def _build_plan(self, original_intent: str, data: Dict[str, Any]) -> WorkflowPlan:
        """Build a WorkflowPlan from parsed JSON, sanitizing steps."""
        raw_steps = data.get("steps", [])
        steps: List[WorkflowStep] = []

        for idx, raw in enumerate(raw_steps):
            action = raw.get("action", "")
            if action not in ALLOWED_ACTIONS:
                # Replace disallowed action with a clarification gate
                steps.append(
                    WorkflowStep(
                        id=f"{idx+1}-sanitized",
                        app="system",
                        action="ask_human",
                        description=f"Planner suggested disallowed action '{action}' — needs clarification",
                        params={"question": f"The planner suggested '{action}' which is not allowed. How should I proceed?"},
                        requires_decision=True,
                    )
                )
                continue

            steps.append(
                WorkflowStep(
                    id=raw.get("id", str(idx + 1)),
                    app=raw.get("app", "system"),
                    action=action,
                    description=raw.get("description", ""),
                    params=raw.get("params", {}),
                    verification=raw.get("verification"),
                    requires_decision=raw.get("requires_decision", False),
                )
            )

        # Ensure there's always a return_result at the end if missing
        if not steps or steps[-1].action != "return_result":
            steps.append(
                WorkflowStep(
                    id=str(len(steps) + 1),
                    app="system",
                    action="return_result",
                    description="Return workflow result",
                    params={"summary": "Workflow completed."},
                )
            )

        return WorkflowPlan(
            intent=original_intent,
            apps_required=data.get("apps_required", []),
            steps=steps,
            estimated_budget=data.get("estimated_budget", 20),
            result_type=data.get("result_type", "summary"),
        )

    def _fallback_plan(self, intent: str, reason: str) -> WorkflowPlan:
        """Return a safe fallback plan that asks the user for clarification."""
        return WorkflowPlan(
            intent=intent,
            apps_required=[],
            steps=[
                WorkflowStep(
                    id="1",
                    app="system",
                    action="ask_human",
                    description=f"Planner failed ({reason}). Need clarification.",
                    params={"question": f"I couldn't plan that workflow ({reason}). Can you describe what you'd like me to do?"},
                    requires_decision=True,
                ),
                WorkflowStep(
                    id="2",
                    app="system",
                    action="return_result",
                    description="Awaiting user input",
                    params={"summary": "Awaiting clarification."},
                ),
            ],
            estimated_budget=5,
            result_type="summary",
        )
