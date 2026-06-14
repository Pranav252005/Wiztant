"""
core/agent_prompts.py — Prompt templates for the Three-Brain Agent system.

Planner (Qwen3-VL), Vision (Gemini Flash), and Executor (UI-TARS)
 each have optimized system prompts and formatting helpers.
"""
from __future__ import annotations

from typing import Any, Dict, List

# =============================================================
#  PLANNER — Qwen3-VL-235B
# =============================================================

PLANNER_SYSTEM_PROMPT = """\
You are Wiztant's Planner. You translate user app ideas into structured execution plans for agentic IDEs.

You NEVER write code. You only create plans, UI specifications, and prompts.

Rules:
1. Analyze the screenshot to understand the current IDE state.
2. Break the task into milestones with clear verification cues.
3. Estimate step counts realistically.
4. Include UI specs when the task involves visual components.
5. Return ONLY valid JSON.
"""


def format_planner_user_message(
    user_spec: str,
    screenshot_b64: str,
    history: List[Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    """Build the user message block for the planner model."""
    history_text = ""
    if history:
        history_text = "\nExecution history:\n" + "\n".join(
            f"  Step {h.get('step', '?')}: {h.get('action', '?')} — {h.get('status', '?')}"
            for h in history[-10:]
        )
    return [
        {
            "type": "text",
            "text": (
                f"User specification: {user_spec}\n"
                f"{history_text}\n\n"
                f"Return a structured plan as JSON with this exact schema:\n"
                f'{{"plan_id": "uuid", "detected_tool": "cursor|windsurf|vscode", '
                f'"tool_confidence": 0.0-1.0, "estimated_steps": N, '
                f'"milestones": [{{"step_id": N, "title": "...", "prompt": "...", '
                f'"expected_ide_actions": N, "verification_cues": ["..."], "status": "pending"}}]}}'
            ),
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{screenshot_b64}"},
        },
    ]


# =============================================================
#  VISION — Gemini 3 Flash
# =============================================================

VISION_SYSTEM_PROMPT = """\
You are Wiztant's Vision Brain. You analyze screenshots of the user's desktop and IDE.

Your job is to:
1. Identify the active tool (Cursor, Windsurf, VS Code, etc.)
2. Describe the window state (chat open, generating, idle, error)
3. Locate key UI elements with normalized coordinates (0.0-1.0)
4. Detect errors, loading states, and completion signals
5. Suggest the next action

Return ONLY valid JSON with this schema:
{
  "tool_detected": "cursor|windsurf|vscode|unknown",
  "tool_confidence": 0.0-1.0,
  "window_state": "chat_panel_open|composer_open|idle|generating|error",
  "is_loading": false,
  "is_generating": false,
  "last_message_status": "completed|generating|error|idle",
  "visible_elements": {
    "chat_input_box": {"x_norm": 0.0, "y_norm": 0.0, "visible": true},
    "send_button": {"x_norm": 0.0, "y_norm": 0.0, "visible": false}
  },
  "detected_errors": [],
  "suggested_next_action": "ready_for_prompt|wait_for_generation|click_revert"
}
"""


def format_vision_user_message(screenshot_b64: str, question: str | None = None) -> List[Dict[str, Any]]:
    """Build the user message block for the vision model."""
    text = question or (
        "Analyze this screenshot. Identify the IDE, window state, visible UI elements, "
        "and any errors or completion signals. Return JSON."
    )
    return [
        {"type": "text", "text": text},
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{screenshot_b64}"},
        },
    ]


def format_verify_change_message(
    before_b64: str, after_b64: str, expected_action: str
) -> List[Dict[str, Any]]:
    """Ask vision model to verify a change occurred after an action."""
    return [
        {
            "type": "text",
            "text": (
                f"Did the screen change after this action: '{expected_action}'?\n"
                f"Compare the BEFORE and AFTER screenshots.\n"
                f'Return JSON: {{"changed": true|false, "description": "what changed", '
                f'"completion_detected": true|false}}'
            ),
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{before_b64}"},
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{after_b64}"},
        },
    ]


# =============================================================
#  EXECUTOR — UI-TARS 1.5-7B
# =============================================================

EXECUTOR_SYSTEM_PROMPT = """\
You are a GUI automation agent. Given a screenshot and a task, output ONLY the next action(s) needed.

Use normalized coordinates (0.0-1.0) where (0,0) is top-left and (1,1) is bottom-right.

Available actions:
- CLICK(x,y)
- DOUBLE_CLICK(x,y)
- TYPE(text)
- PRESS(key)
- SCROLL(dir,amount)  // dir: up|down, amount: lines
- WAIT(seconds)
- DRAG(x1,y1,x2,y2)

Rules:
1. Output ONLY actions, one per line. No explanations.
2. Click BEFORE typing to focus.
3. Press Enter after typing a prompt.
4. Wait after pressing Enter to let the IDE respond.
5. If an element isn't visible, scroll to find it.
"""


def format_executor_user_message(
    screenshot_b64: str,
    task: str,
    hints: Dict[str, Any] | None = None,
    history: List[str] | None = None,
) -> List[Dict[str, Any]]:
    """Build the user message block for UI-TARS."""
    hints_text = ""
    if hints:
        hints_text = "\nHints:\n" + "\n".join(
            f"  {k}: {v}" for k, v in hints.items()
        )
    history_text = ""
    if history:
        history_text = "\nLast actions:\n" + "\n".join(f"  {h}" for h in history[-5:])
    return [
        {
            "type": "text",
            "text": (
                f"Task: {task}{hints_text}{history_text}\n\n"
                f"Output ONLY the next action(s):"
            ),
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{screenshot_b64}"},
        },
    ]
