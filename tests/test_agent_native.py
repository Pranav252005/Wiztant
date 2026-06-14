"""
tests/test_agent_native.py — Tests for the Three-Brain Agent system.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is on path
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

import pytest

from core.agent_actions import (
    parse_ui_tars_output,
    count_step_cost,
    ActionExecutor,
    ClickAction,
    TypeAction,
    PressAction,
    ScrollAction,
    WaitAction,
    DoubleClickAction,
    DragAction,
)
from core.agent_state import (
    AgentSession,
    AgentStateMachine,
    AgentPlan,
    Milestone,
    SessionStatus,
    StepBudgetExceeded,
)
from core.agent_profiles import get_profile, detect_tool_from_text, CursorProfile, WindsurfProfile
from core.agent_prompts import (
    format_planner_user_message,
    format_vision_user_message,
    format_executor_user_message,
)


# =============================================================
#  ACTION PARSING
# =============================================================

class TestActionParsing:
    def test_parse_click(self):
        raw = "CLICK(0.12,0.89)"
        actions = parse_ui_tars_output(raw)
        assert len(actions) == 1
        assert isinstance(actions[0], ClickAction)
        assert actions[0].x_norm == 0.12
        assert actions[0].y_norm == 0.89

    def test_parse_type(self):
        raw = 'TYPE("hello world")'
        actions = parse_ui_tars_output(raw)
        assert len(actions) == 1
        assert isinstance(actions[0], TypeAction)
        assert actions[0].text == "hello world"
        assert actions[0].step_cost == 1.0

    def test_parse_long_type_cost(self):
        raw = f'TYPE("{"x" * 150}")'
        actions = parse_ui_tars_output(raw)
        assert actions[0].step_cost == 2.0

    def test_parse_press(self):
        raw = 'PRESS("enter")'
        actions = parse_ui_tars_output(raw)
        assert len(actions) == 1
        assert isinstance(actions[0], PressAction)
        assert actions[0].key == "enter"
        assert actions[0].step_cost == 0.5

    def test_parse_scroll(self):
        raw = 'SCROLL("down",3)'
        actions = parse_ui_tars_output(raw)
        assert len(actions) == 1
        assert isinstance(actions[0], ScrollAction)
        assert actions[0].direction == "down"
        assert actions[0].amount == 3

    def test_parse_wait(self):
        raw = "WAIT(2.5)"
        actions = parse_ui_tars_output(raw)
        assert len(actions) == 1
        assert isinstance(actions[0], WaitAction)
        assert actions[0].seconds == 2.5
        assert actions[0].step_cost == 0.0

    def test_parse_double_click(self):
        raw = "DOUBLE_CLICK(0.45,0.67)"
        actions = parse_ui_tars_output(raw)
        assert len(actions) == 1
        assert isinstance(actions[0], DoubleClickAction)
        assert actions[0].x_norm == 0.45
        assert actions[0].y_norm == 0.67

    def test_parse_drag(self):
        raw = "DRAG(0.1,0.2,0.3,0.4)"
        actions = parse_ui_tars_output(raw)
        assert len(actions) == 1
        assert isinstance(actions[0], DragAction)
        assert actions[0].x1_norm == 0.1
        assert actions[0].y2_norm == 0.4
        assert actions[0].step_cost == 2.0

    def test_parse_multiple_actions(self):
        raw = "CLICK(0.12,0.89)\nTYPE(\"test\")\nPRESS(\"enter\")"
        actions = parse_ui_tars_output(raw)
        assert len(actions) == 3
        assert isinstance(actions[0], ClickAction)
        assert isinstance(actions[1], TypeAction)
        assert isinstance(actions[2], PressAction)

    def test_parse_empty(self):
        assert parse_ui_tars_output("") == []
        assert parse_ui_tars_output("   ") == []

    def test_parse_unrecognized(self):
        raw = "UNKNOWN(1,2,3)"
        actions = parse_ui_tars_output(raw)
        assert actions == []


# =============================================================
#  STEP BUDGET
# =============================================================

class TestStepBudget:
    def test_count_step_cost(self):
        actions = [
            ClickAction(0.5, 0.5),
            TypeAction("short"),
            PressAction("enter"),
            WaitAction(1.0),
        ]
        assert count_step_cost(actions) == 1.0 + 1.0 + 0.5 + 0.0

    def test_state_machine_budget_enforcement(self):
        session = AgentSession(steps_budget=5)
        sm = AgentStateMachine(session)
        sm.consume_steps(3.0)
        assert session.steps_used == 3.0
        sm.consume_steps(1.5)
        assert session.steps_used == 4.5
        with pytest.raises(StepBudgetExceeded):
            sm.consume_steps(1.0)

    def test_budget_warnings(self):
        session = AgentSession(steps_budget=10)
        sm = AgentStateMachine(session)
        # Should not raise at 80%
        sm.consume_steps(8.0)
        assert session.steps_used == 8.0


# =============================================================
#  STATE MACHINE
# =============================================================

class TestStateMachine:
    def test_transitions(self):
        session = AgentSession()
        sm = AgentStateMachine(session)
        assert session.status == SessionStatus.IDLE

        sm.start_planning()
        assert session.status == SessionStatus.PLANNING

        sm.start_execution()
        assert session.status == SessionStatus.RUNNING

        sm.pause("test")
        assert session.status == SessionStatus.PAUSED
        assert sm.is_paused

        sm.resume()
        assert session.status == SessionStatus.RUNNING
        assert not sm.is_paused

        sm.complete()
        assert session.status == SessionStatus.COMPLETED

    def test_save_load(self, tmp_path):
        session = AgentSession(
            plan=AgentPlan(
                plan_id="test-plan",
                milestones=[Milestone(step_id=1, title="M1")],
            ),
            steps_used=5.0,
            current_step=1,
        )
        sm = AgentStateMachine(session)
        path = tmp_path / "session.json"
        sm.save(path)

        loaded = AgentStateMachine.load(path)
        assert loaded.session.session_id == session.session_id
        assert loaded.session.steps_used == 5.0
        assert loaded.session.plan is not None
        assert loaded.session.plan.plan_id == "test-plan"


# =============================================================
#  TOOL PROFILES
# =============================================================

class TestToolProfiles:
    def test_cursor_profile(self):
        p = get_profile("cursor")
        assert p.name == "cursor"
        assert p.chat_input_selector == (0.12, 0.89)
        assert "@codebase" in p.format_prompt("test")

    def test_windsurf_profile(self):
        p = get_profile("windsurf")
        assert p.name == "windsurf"
        assert "@@file" in p.format_prompt("test")

    def test_detect_tool_from_text(self):
        assert detect_tool_from_text("Open cursor and build a component") == "cursor"
        assert detect_tool_from_text("Use windsurf to refactor") == "windsurf"
        assert detect_tool_from_text("Random text") is None

    def test_unknown_profile_fallback(self):
        p = get_profile("unknown_tool")
        assert p.name == "unknown_tool"
        assert p.chat_input_selector == (0.0, 0.0)


# =============================================================
#  PROMPT FORMATTING
# =============================================================

class TestPromptFormatting:
    def test_planner_message_structure(self):
        msgs = format_planner_user_message("build app", "fakeb64")
        assert len(msgs) == 2
        assert msgs[0]["type"] == "text"
        assert "build app" in msgs[0]["text"]
        assert msgs[1]["type"] == "image_url"

    def test_vision_message_structure(self):
        msgs = format_vision_user_message("fakeb64")
        assert len(msgs) == 2
        assert "Analyze this screenshot" in msgs[0]["text"]

    def test_executor_message_structure(self):
        msgs = format_executor_user_message("fakeb64", "click the button")
        assert len(msgs) == 2
        assert "click the button" in msgs[0]["text"]


# =============================================================
#  ACTION EXECUTOR (MOCKED RUNTIME)
# =============================================================

class TestActionExecutor:
    def test_coordinate_conversion(self):
        mock_runtime = MagicMock()
        mock_runtime.screen_size.return_value = (1920, 1080)
        mock_runtime.click.return_value = (True, "ok")

        exec = ActionExecutor(mock_runtime)
        action = ClickAction(x_norm=0.5, y_norm=0.5)
        ok, msg = exec.execute(action)

        # Should convert 0.5,0.5 to 960,540
        mock_runtime.click.assert_called_once_with(960, 540, button="left")
        assert ok is True

    def test_safety_bounds_clamping(self):
        mock_runtime = MagicMock()
        mock_runtime.screen_size.return_value = (1920, 1080)
        mock_runtime.click.return_value = (True, "ok")

        exec = ActionExecutor(mock_runtime)
        action = ClickAction(x_norm=1.5, y_norm=-0.2)
        exec.execute(action)

        # Should clamp to screen bounds
        call_args = mock_runtime.click.call_args
        x, y = call_args[0][0], call_args[0][1]
        assert 1 <= x <= 1919
        assert 1 <= y <= 1079

    def test_execute_many(self):
        mock_runtime = MagicMock()
        mock_runtime.screen_size.return_value = (1920, 1080)
        mock_runtime.click.return_value = (True, "ok")
        mock_runtime.type_text.return_value = (True, "ok")

        exec = ActionExecutor(mock_runtime)
        actions = [ClickAction(0.1, 0.1), TypeAction("hello")]
        cost, msgs = exec.execute_many(actions)

        assert cost == 2.0
        assert len(msgs) == 2


# =============================================================
#  INTEGRATION: ORCHESTRATOR IMPORTS
# =============================================================

class TestOrchestratorImports:
    def test_all_imports(self):
        """Verify all new modules can be imported."""
        from core.agent_orchestrator import run_agent_session
        from core.agent_planner import PlannerBrain
        from core.agent_vision import VisionBrain
        from core.agent_executor import ExecutorBrain
        from core.agent_actions import ActionExecutor
        from core.agent_state import AgentStateMachine
        from core.agent_profiles import get_profile
        from core.agent_screenshots import ScreenshotManager
        from core.agent_prompts import PLANNER_SYSTEM_PROMPT

        assert callable(run_agent_session)
        assert PlannerBrain is not None
        assert VisionBrain is not None
        assert ExecutorBrain is not None
