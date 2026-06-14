"""Tests for core/workflow_planner.py — Workflow Planner (NL → WorkflowPlan)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.workflow_planner import WorkflowPlanner
from core.workflow_runtime import WorkflowPlan, WorkflowStep, ALLOWED_ACTIONS


class TestWorkflowPlanner:
    """Test suite for WorkflowPlanner intent-to-plan conversion."""

    def test_planner_returns_workflow_plan(self):
        """A clear intent should produce a valid WorkflowPlan."""
        planner = WorkflowPlanner()
        mock_response = '''
        {
            "intent": "Check Jira tickets",
            "apps_required": ["browser"],
            "steps": [
                {"id": "1", "app": "browser", "action": "open_app", "description": "Open browser", "params": {"app_name": "chrome"}},
                {"id": "2", "app": "browser", "action": "navigate_to", "description": "Go to Jira", "params": {"url": "https://jira.example.com"}},
                {"id": "3", "app": "browser", "action": "read_screen", "description": "Read ticket list", "params": {}},
                {"id": "4", "app": "browser", "action": "return_result", "description": "Return highest priority", "params": {"summary": "Highest priority ticket is PROJ-42"}}
            ],
            "estimated_budget": 10,
            "result_type": "summary"
        }
        '''
        with patch("core.workflow_planner.call_api", return_value=mock_response):
            plan = planner.plan("Check my Jira tickets and tell me the highest priority one")

        assert isinstance(plan, WorkflowPlan)
        assert len(plan.steps) == 4
        assert plan.steps[0].action == "open_app"
        assert plan.steps[1].action == "navigate_to"
        assert plan.steps[3].action == "return_result"
        assert "browser" in plan.apps_required

    def test_planner_never_emits_blocked_actions(self):
        """If the LLM returns a blocked action, it must be replaced with ask_human."""
        planner = WorkflowPlanner()
        mock_response = '''
        {
            "intent": "Do bad thing",
            "apps_required": ["terminal"],
            "steps": [
                {"id": "1", "app": "terminal", "action": "create_file", "description": "Write file", "params": {"path": "/tmp/bad.txt"}},
                {"id": "2", "app": "terminal", "action": "open_app", "description": "Open terminal", "params": {"app_name": "terminal"}}
            ],
            "estimated_budget": 5,
            "result_type": "summary"
        }
        '''
        with patch("core.workflow_planner.call_api", return_value=mock_response):
            plan = planner.plan("Do something")

        # create_file should have been stripped/replaced
        actions = [s.action for s in plan.steps]
        assert "create_file" not in actions
        assert "git_commit" not in actions
        assert "open_app" in actions

    def test_malformed_intent_uses_ask_human(self):
        """A vague intent should include an ask_human step for clarification."""
        planner = WorkflowPlanner()
        mock_response = '''
        {
            "intent": "Vague request",
            "apps_required": [],
            "steps": [
                {"id": "1", "app": "system", "action": "ask_human", "description": "Clarify intent", "params": {"question": "What would you like me to do?"}}
            ],
            "estimated_budget": 5,
            "result_type": "summary"
        }
        '''
        with patch("core.workflow_planner.call_api", return_value=mock_response):
            plan = planner.plan("Do something")

        assert any(s.action == "ask_human" for s in plan.steps)

    def test_planner_handles_invalid_json_gracefully(self):
        """If the LLM returns garbage, planner should return a safe fallback plan."""
        planner = WorkflowPlanner()
        with patch("core.workflow_planner.call_api", return_value="not json at all"):
            plan = planner.plan("Check my email")

        assert isinstance(plan, WorkflowPlan)
        assert len(plan.steps) >= 1
        assert plan.steps[0].action == "ask_human"

    def test_all_returned_actions_are_in_allowed_set(self):
        """Every step action in the final plan must be in ALLOWED_ACTIONS."""
        planner = WorkflowPlanner()
        mock_response = '''
        {
            "intent": "Test",
            "apps_required": ["browser"],
            "steps": [
                {"id": "1", "app": "browser", "action": "open_app", "description": "Open", "params": {}},
                {"id": "2", "app": "browser", "action": "click", "description": "Click", "params": {"x": 100, "y": 200}},
                {"id": "3", "app": "browser", "action": "type", "description": "Type", "params": {"text": "hello"}},
                {"id": "4", "app": "browser", "action": "return_result", "description": "Done", "params": {"summary": "Done"}}
            ],
            "estimated_budget": 5,
            "result_type": "summary"
        }
        '''
        with patch("core.workflow_planner.call_api", return_value=mock_response):
            plan = planner.plan("Test")

        for step in plan.steps:
            assert step.action in ALLOWED_ACTIONS, f"{step.action} is not allowed"
