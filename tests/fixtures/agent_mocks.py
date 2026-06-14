"""
Mock brains and runtime for deterministic agent lifecycle testing.

These mocks replace the real Planner, Vision, Executor, ScreenshotManager,
and ActionExecutor so that `run_agent_session` can run without:
  - OpenRouter API keys
  - Real screenshots (mss / desktop)
  - Real mouse/keyboard input (pyautogui)
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional
from PIL import Image

from core.agent_state import AgentPlan, Milestone
from core.agent_actions import (
    AgentAction,
    ClickAction,
    TypeAction,
    PressAction,
    WaitAction,
)

# ── Shared deterministic image ───────────────────────────────────────────────
_BLANK_IMG = Image.new("RGB", (1920, 1080), color=(30, 30, 40))


def _img_hash(img: Image.Image) -> str:
    """Consistent hash for a PIL image."""
    thumb = img.resize((32, 32), Image.Resampling.LANCZOS).convert("L")
    return hashlib.md5(thumb.tobytes()).hexdigest()


# ── Mock Screenshot Manager ──────────────────────────────────────────────────
class MockScreenshotManager:
    """Returns deterministic images and hashes."""

    def __init__(self, sequence: list[Image.Image] | None = None):
        self._sequence = sequence or []
        self._index = 0
        self._last_hash = ""

    def capture(self, monitor_index: int | None = None) -> Image.Image:
        if self._index < len(self._sequence):
            img = self._sequence[self._index]
            self._index += 1
            return img
        # Vary the blank image so each screenshot has a different hash
        import random
        random.seed(self._index)
        self._index += 1
        img = _BLANK_IMG.copy()
        # Draw a small colored square in the corner so resize preserves the difference
        color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        for x in range(20):
            for y in range(20):
                img.putpixel((x, y), color)
        return img

    def capture_active_window(self, runtime=None) -> Image.Image:
        return self.capture()

    def quick_hash(self, img: Image.Image) -> str:
        return _img_hash(img)

    def has_changed(self, img: Image.Image) -> bool:
        h = self.quick_hash(img)
        changed = h != self._last_hash
        self._last_hash = h
        return changed


# ── Mock Planner ─────────────────────────────────────────────────────────────
class MockPlannerBrain:
    """Returns a predefined multi-milestone plan."""

    def __init__(self, milestones: list[Milestone] | None = None):
        if milestones is None:
            milestones = [
                Milestone(step_id=1, title="Open IDE", prompt="Open VS Code:"),
                Milestone(step_id=2, title="Create file", prompt="Create calculator.py"),
                Milestone(step_id=3, title="Write code", prompt="Write Calculator class"),
                Milestone(step_id=4, title="Save and run", prompt="Save and run the file"),
            ]
        self._milestones = milestones

    def create_plan(self, user_spec: str, screenshot, history=None) -> AgentPlan:
        return AgentPlan(
            plan_id="mock-plan",
            detected_tool="vscode",
            tool_confidence=0.95,
            estimated_steps=len(self._milestones) * 2,
            milestones=[Milestone(**m.__dict__) for m in self._milestones],
        )

    def replan(self, original_plan, new_spec, screenshot, execution_history, steps_remaining):
        return original_plan


# ── Mock Vision ──────────────────────────────────────────────────────────────
class MockVisionBrain:
    """
    Cycles through IDE states to exercise every branch of the orchestrator.

    States:
      0  idle          → normal
      1  typing        → normal
      2  error         → triggers auto-pause (ide_error_detected)
      3  completed     → milestone complete pause
      4  idle (resume) → normal
      5  idle          → no visible change (triggers warning)
      6  idle          → normal, then loop
      7  idle          → final completion
    """

    def __init__(self, states: list[Dict[str, Any]] | None = None):
        if states is None:
            states = [
                {"window_state": "idle", "detected_errors": [], "last_message_status": "idle", "visible_elements": {}},
                {"window_state": "typing", "detected_errors": [], "last_message_status": "idle", "visible_elements": {"editor": {"x_norm": 0.5, "y_norm": 0.5}}},
                {"window_state": "error_popup", "detected_errors": ["SyntaxError"], "last_message_status": "idle", "visible_elements": {}},
                {"window_state": "idle", "detected_errors": [], "last_message_status": "completed", "visible_elements": {}},
                {"window_state": "idle", "detected_errors": [], "last_message_status": "idle", "visible_elements": {}},
                {"window_state": "idle", "detected_errors": [], "last_message_status": "idle", "visible_elements": {}},
                {"window_state": "idle", "detected_errors": [], "last_message_status": "idle", "visible_elements": {}},
                {"window_state": "terminal_output", "detected_errors": [], "last_message_status": "completed", "visible_elements": {}},
            ]
        self._states = states
        self._idx = 0
        self._last_result: Dict[str, Any] | None = None

    def analyze(self, screenshot, question=None) -> Dict[str, Any]:
        state = self._states[min(self._idx, len(self._states) - 1)]
        self._idx += 1
        self._last_result = state
        return state

    def verify_change(self, before_screenshot, after_screenshot, expected_action: str):
        # Always report changed for simplicity
        return {"changed": True, "description": "mock change", "completion_detected": False}

    def detects_completion(self) -> bool:
        if self._last_result is None:
            return False
        return self._last_result.get("last_message_status", "").lower() in ("completed", "done", "finished")

    def detects_error(self) -> bool:
        if self._last_result is None:
            return False
        return bool(self._last_result.get("detected_errors", []))


# ── Mock Executor ────────────────────────────────────────────────────────────
class MockExecutorBrain:
    """
    Returns a scripted sequence of actions.
    The sequence includes one blocked action (rm -rf) so guardrails fire,
    and duplicate actions so loop detection fires.
    """

    def __init__(self, actions: list[list[AgentAction]] | None = None):
        if actions is None:
            actions = [
                [ClickAction(x_norm=0.12, y_norm=0.89)],                       # step 1
                [TypeAction(text="calculator.py")],                            # step 2
                [TypeAction(text="rm -rf /")],                                 # step 3 → guardrail blocked
                [PressAction(key="enter")],                                    # step 4
                [WaitAction(seconds=1.5)],                                      # step 5
                [ClickAction(x_norm=0.12, y_norm=0.89)],                       # step 6 → duplicate (loop)
                [ClickAction(x_norm=0.12, y_norm=0.89)],                       # step 7 → duplicate (loop)
                [PressAction(key="ctrl+s")],                                   # step 8
                [TypeAction(text="python calculator.py")],                     # step 9
                [PressAction(key="enter")],                                    # step 10
            ]
        self._actions = actions
        self._idx = 0

    def predict(self, screenshot, task: str, hints=None, history=None):
        actions = self._actions[min(self._idx, len(self._actions) - 1)]
        self._idx += 1
        return actions

    def predict_with_retry(self, screenshot, task, hints=None, history=None, max_retries=2):
        return self.predict(screenshot, task, hints, history)


# ── Mock Action Executor ─────────────────────────────────────────────────────
class MockActionExecutor:
    """No-op action execution that just logs what it received."""

    def __init__(self, runtime=None):
        self._runtime = runtime
        self.executed: list[str] = []

    def execute(self, action: AgentAction) -> tuple[bool, str]:
        name = type(action).__name__
        self.executed.append(name)
        return True, f"mock-{name}"

    def execute_many(self, actions: list[AgentAction]):
        messages: list[str] = []
        for a in actions:
            ok, msg = self.execute(a)
            messages.append(msg)
        from core.agent_actions import count_step_cost
        return count_step_cost(actions), messages


# ── Mock Runtime ─────────────────────────────────────────────────────────────
class MockAgentRuntime:
    """Minimal runtime that provides screen size but does no real input."""

    def screen_size(self):
        return (1920, 1080)

    def click(self, x, y, button="left"):
        pass

    def type_text(self, text):
        pass

    def press_key(self, key):
        pass
