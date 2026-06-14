"""Tests for core/workflow_templates.py — Daily-life workflow templates."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.workflow_templates import TemplateRegistry, WorkflowTemplate
from core.workflow_runtime import WorkflowPlan, WorkflowStep


class TestTemplateRegistry:
    """Test suite for workflow template resolution."""

    def test_resolve_morning_standup(self):
        """morning_standup template should resolve to a plan with browser and slack steps."""
        registry = TemplateRegistry()
        plan = registry.resolve("morning_standup", {})

        assert isinstance(plan, WorkflowPlan)
        assert "browser" in plan.apps_required
        assert "slack" in plan.apps_required
        actions = [s.action for s in plan.steps]
        assert "open_app" in actions
        assert "return_result" in actions

    def test_resolve_ticket_to_slack(self):
        """ticket_to_slack should include jira and slack apps."""
        registry = TemplateRegistry()
        plan = registry.resolve("ticket_to_slack", {"description": "Login bug"})

        assert isinstance(plan, WorkflowPlan)
        assert "browser" in plan.apps_required
        actions = [s.action for s in plan.steps]
        assert "navigate_to" in actions or "open_app" in actions

    def test_resolve_info_gather_uses_planner(self):
        """info_gather should delegate to the dynamic planner."""
        registry = TemplateRegistry()
        mock_plan = WorkflowPlan(
            intent="Gather info",
            apps_required=["browser"],
            steps=[
                WorkflowStep(id="1", app="browser", action="open_app", params={"app_name": "chrome"}),
                WorkflowStep(id="2", app="system", action="return_result", params={"summary": "Done"}),
            ],
        )
        with patch.object(registry._planner, "plan", return_value=mock_plan):
            plan = registry.resolve("info_gather", {"query": "weather today"})

        assert isinstance(plan, WorkflowPlan)
        assert plan.steps[0].action == "open_app"

    def test_parameter_injection(self):
        """User params should be injected into template step params."""
        registry = TemplateRegistry()
        plan = registry.resolve("ticket_to_slack", {"channel": "#engineering", "description": "Login bug"})

        # At least one step should have the channel injected
        param_values = []
        for step in plan.steps:
            param_values.extend(step.params.values())
        assert any("#engineering" in str(v) for v in param_values)
        assert any("Login bug" in str(v) for v in param_values)

    def test_unknown_preset_returns_fallback(self):
        """An unknown preset ID should return a safe fallback plan."""
        registry = TemplateRegistry()
        plan = registry.resolve("nonexistent_preset", {})

        assert isinstance(plan, WorkflowPlan)
        assert any(s.action == "ask_human" for s in plan.steps)

    def test_all_templates_have_required_fields(self):
        """Every built-in template must have id, name, apps_required."""
        registry = TemplateRegistry()
        for template in registry._templates.values():
            assert template.id
            assert template.name
            assert isinstance(template.apps_required, list)

    def test_email_triage_template(self):
        """email_triage should be resolvable."""
        registry = TemplateRegistry()
        plan = registry.resolve("email_triage", {})
        assert isinstance(plan, WorkflowPlan)
        assert len(plan.steps) > 0
