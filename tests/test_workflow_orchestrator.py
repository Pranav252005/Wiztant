"""Tests for core/agent_v2_orchestrator.py — Workflow Orchestrator."""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agent_v2_orchestrator import WorkflowOrchestrator
from core.workflow_runtime import WorkflowPlan, WorkflowStep


def _make_simple_plan() -> WorkflowPlan:
    """Return a simple test plan."""
    return WorkflowPlan(
        intent="Test plan",
        apps_required=["browser"],
        steps=[
            WorkflowStep(id="1", app="browser", action="open_app", params={"app_name": "chrome"}),
            WorkflowStep(id="2", app="browser", action="navigate_to", params={"url": "https://example.com"}),
            WorkflowStep(id="3", app="system", action="return_result", params={"summary": "Done"}),
        ],
    )


class TestWorkflowOrchestrator:
    """Test suite for the WorkflowOrchestrator integration."""

    def test_initiate_runs_plan_and_delivers_result(self):
        """Orchestrator should run a plan and deliver a result."""
        orch = WorkflowOrchestrator()
        mock_runtime = MagicMock()
        mock_runtime.execute.return_value = None
        mock_runtime.action_log = [
            {"action": "open_app", "params": {"app_name": "chrome"}, "result": "chrome"},
            {"action": "navigate_to", "params": {"url": "https://example.com"}, "result": True},
            {"action": "return_result", "params": {"summary": "Done"}, "result": "Done"},
        ]
        mock_runtime.finalized = True
        mock_runtime.result_summary = "Done"

        mock_result = MagicMock()
        mock_result.summarize.return_value = "Workflow completed successfully."
        orch._result_deliverer = mock_result

        with patch("core.agent_v2_orchestrator.WorkflowRuntime", return_value=mock_runtime):
            with patch("core.agent_v2_orchestrator.broadcast_sync") as mock_broadcast:
                with patch("core.agent_v2_orchestrator.get_system_access") as mock_sys:
                    mock_sys.return_value = MagicMock()
                    with patch.object(orch._registry, "resolve", return_value=_make_simple_plan()):
                        orch.initiate("info_gather", {"query": "test"})

        # Verify result was summarized and delivered
        mock_result.summarize.assert_called_once()
        mock_result.deliver.assert_called_once_with("Workflow completed successfully.", mock_broadcast, mock_sys.return_value)

    def test_initiate_with_static_template(self):
        """Orchestrator should resolve static templates correctly."""
        orch = WorkflowOrchestrator()
        mock_runtime = MagicMock()
        mock_runtime.execute.return_value = None
        mock_runtime.action_log = []
        mock_runtime.finalized = True
        mock_runtime.result_summary = "Standup posted."

        mock_result = MagicMock()
        mock_result.summarize.return_value = "Standup posted to #standup."
        orch._result_deliverer = mock_result

        with patch("core.agent_v2_orchestrator.WorkflowRuntime", return_value=mock_runtime):
            with patch("core.agent_v2_orchestrator.broadcast_sync"):
                with patch("core.agent_v2_orchestrator.get_system_access") as mock_sys:
                    mock_sys.return_value = MagicMock()
                    orch.initiate("morning_standup", {"channel": "#standup"})

        # Should have executed at least open_app and return_result
        actions = [c[0][0] for c in mock_runtime.execute.call_args_list]
        assert "open_app" in actions
        assert "return_result" in actions

    def test_gate_pause_and_resume(self):
        """Orchestrator should pause at gates and resume after decision."""
        orch = WorkflowOrchestrator()
        gate_plan = WorkflowPlan(
            intent="Approval loop",
            apps_required=["browser"],
            steps=[
                WorkflowStep(id="1", app="browser", action="open_app", params={"app_name": "chrome"}),
                WorkflowStep(id="2", app="system", action="ask_human", params={"question": "Approve?", "timeout": 5}),
                WorkflowStep(id="3", app="system", action="return_result", params={"summary": "Done"}),
            ],
        )
        mock_runtime = MagicMock()
        mock_runtime.execute.side_effect = lambda action, **kwargs: (
            {"type": "gate_request", "question": "Approve?", "timeout": 5} if action == "ask_human" else
            "Done" if action == "return_result" else None
        )
        mock_runtime.action_log = []
        mock_runtime.finalized = True
        mock_runtime.result_summary = "Done"

        mock_result = MagicMock()
        mock_result.summarize.return_value = "Done."
        orch._result_deliverer = mock_result

        with patch("core.agent_v2_orchestrator.WorkflowRuntime", return_value=mock_runtime):
            with patch("core.agent_v2_orchestrator.broadcast_sync"):
                with patch("core.agent_v2_orchestrator.get_system_access") as mock_sys:
                    mock_sys.return_value = MagicMock()
                    with patch.object(orch._registry, "resolve", return_value=gate_plan):
                        # Run in a thread so we can resolve the gate asynchronously
                        result = [None]
                        def run():
                            result[0] = orch.initiate("approval_loop", {"approvals_url": "https://jira.example.com"})
                        t = threading.Thread(target=run)
                        t.start()
                        # Give it time to reach the gate
                        time.sleep(0.2)
                        # Resolve the gate
                        gate_keys = list(orch.gate_manager._gates.keys())
                        assert len(gate_keys) > 0, "Gate was not created"
                        orch.gate_manager.resolve(gate_keys[0], "yes")
                        t.join(timeout=3)
                        assert not t.is_alive()

    def test_error_handling_retries_once(self):
        """On step error, orchestrator should retry once then fail gracefully."""
        orch = WorkflowOrchestrator()
        error_plan = WorkflowPlan(
            intent="Error test",
            apps_required=["browser"],
            steps=[
                WorkflowStep(id="1", app="browser", action="open_app", params={"app_name": "chrome"}),
                WorkflowStep(id="2", app="browser", action="navigate_to", params={"url": "https://example.com"}),
                WorkflowStep(id="3", app="system", action="return_result", params={"summary": "Done"}),
            ],
        )
        mock_runtime = MagicMock()
        call_count = [0]
        def side_effect(action, **kwargs):
            call_count[0] += 1
            if action == "navigate_to" and call_count[0] <= 2:
                raise RuntimeError("Browser not found")
            return True

        mock_runtime.execute.side_effect = side_effect
        mock_runtime.action_log = []

        mock_result = MagicMock()
        mock_result.summarize.return_value = "Failed: Browser not found."
        orch._result_deliverer = mock_result

        with patch("core.agent_v2_orchestrator.WorkflowRuntime", return_value=mock_runtime):
            with patch("core.agent_v2_orchestrator.broadcast_sync"):
                with patch("core.agent_v2_orchestrator.get_system_access") as mock_sys:
                    mock_sys.return_value = MagicMock()
                    with patch.object(orch._registry, "resolve", return_value=error_plan):
                        orch.initiate("research_digest", {"query": "test"})

        # navigate_to should have been called twice (original + retry)
        navigate_calls = [c for c in mock_runtime.execute.call_args_list if c[0][0] == "navigate_to"]
        assert len(navigate_calls) == 2
