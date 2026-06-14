"""End-to-end integration test for Workflow Mode.

Tests a full ticket-to-slack workflow with mocked platform access.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agent_v2_orchestrator import WorkflowOrchestrator
from core.workflow_runtime import WorkflowPlan, WorkflowStep


def _make_ticket_to_slack_plan() -> WorkflowPlan:
    """Return a simplified ticket-to-slack plan for testing."""
    return WorkflowPlan(
        intent="Create Jira ticket and share to Slack",
        apps_required=["browser", "slack"],
        steps=[
            WorkflowStep(id="1", app="browser", action="open_app", params={"app_name": "chrome"}),
            WorkflowStep(id="2", app="browser", action="navigate_to", params={"url": "https://jira.example.com"}),
            WorkflowStep(id="3", app="browser", action="read_screen", params={}, description="Read ticket status"),
            WorkflowStep(id="4", app="slack", action="open_app", params={"app_name": "slack"}),
            WorkflowStep(id="5", app="slack", action="paste", params={}, description="Paste ticket link"),
            WorkflowStep(id="6", app="system", action="return_result", params={"summary": "Ticket PROJ-42 created and shared."}),
        ],
    )


class TestWorkflowE2E:
    """End-to-end workflow integration tests."""

    def test_ticket_to_slack_workflow(self):
        """Full workflow: create ticket → share to Slack → return result."""
        orch = WorkflowOrchestrator()
        mock_runtime = MagicMock()
        mock_runtime.execute.return_value = None
        mock_runtime.action_log = [
            {"action": "open_app", "params": {"app_name": "chrome"}, "result": "chrome"},
            {"action": "navigate_to", "params": {"url": "https://jira.example.com"}, "result": True},
            {"action": "read_screen", "params": {}, "result": "Ticket PROJ-42 created"},
            {"action": "open_app", "params": {"app_name": "slack"}, "result": "slack"},
            {"action": "paste", "params": {}, "result": True},
            {"action": "return_result", "params": {"summary": "Ticket PROJ-42 created and shared."}, "result": "Ticket PROJ-42 created and shared."},
        ]
        mock_runtime.finalized = True
        mock_runtime.result_summary = "Ticket PROJ-42 created and shared."

        mock_result = MagicMock()
        mock_result.summarize.return_value = "Created ticket PROJ-42 and shared it in Slack."
        orch._result_deliverer = mock_result

        with patch("core.agent_v2_orchestrator.WorkflowRuntime", return_value=mock_runtime):
            with patch("core.agent_v2_orchestrator.broadcast_sync"):
                with patch("core.agent_v2_orchestrator.get_system_access") as mock_sys:
                    mock_sys.return_value = MagicMock()
                    with patch.object(orch._registry, "resolve", return_value=_make_ticket_to_slack_plan()):
                        summary = orch.initiate("ticket_to_slack", {"description": "Login bug", "channel": "#engineering"})

        assert "PROJ-42" in summary
        # Verify no file write actions were attempted
        actions = [c[0][0] for c in mock_runtime.execute.call_args_list]
        assert "create_file" not in actions
        assert "git_commit" not in actions
        assert "edit_file" not in actions

    def test_workflow_with_gate(self):
        """Workflow that hits a decision gate should pause and resume."""
        orch = WorkflowOrchestrator()
        gate_plan = WorkflowPlan(
            intent="Approval needed",
            apps_required=["browser"],
            steps=[
                WorkflowStep(id="1", app="browser", action="open_app", params={"app_name": "chrome"}),
                WorkflowStep(id="2", app="system", action="ask_human", params={"question": "Send this message?", "timeout": 5}),
                WorkflowStep(id="3", app="system", action="return_result", params={"summary": "Message sent."}),
            ],
        )
        mock_runtime = MagicMock()
        mock_runtime.execute.side_effect = lambda action, **kwargs: (
            {"type": "gate_request", "question": "Send this message?", "timeout": 5} if action == "ask_human" else
            "Message sent." if action == "return_result" else None
        )
        mock_runtime.action_log = []
        mock_runtime.finalized = True
        mock_runtime.result_summary = "Message sent."

        mock_result = MagicMock()
        mock_result.summarize.return_value = "Message sent after approval."
        orch._result_deliverer = mock_result

        with patch("core.agent_v2_orchestrator.WorkflowRuntime", return_value=mock_runtime):
            with patch("core.agent_v2_orchestrator.broadcast_sync"):
                with patch("core.agent_v2_orchestrator.get_system_access") as mock_sys:
                    mock_sys.return_value = MagicMock()
                    with patch.object(orch._registry, "resolve", return_value=gate_plan):
                        import threading
                        result = [None]
                        def run():
                            result[0] = orch.initiate("approval_loop", {"approvals_url": "https://jira.example.com"})
                        t = threading.Thread(target=run)
                        t.start()
                        import time
                        time.sleep(0.2)
                        gate_keys = list(orch.gate_manager._gates.keys())
                        assert len(gate_keys) > 0
                        orch.gate_manager.resolve(gate_keys[0], "yes")
                        t.join(timeout=3)
                        assert not t.is_alive()
                        assert "approval" in result[0].lower() or "Message sent" in result[0]

    def test_virtual_desktop_lifecycle(self):
        """Orchestrator should attempt to create and cleanup virtual desktop."""
        orch = WorkflowOrchestrator()
        mock_vd = MagicMock()
        mock_vd.current_desktop.return_value = "0"
        mock_vd.create_desktop.return_value = "1"

        plan = WorkflowPlan(
            intent="Simple test",
            apps_required=[],
            steps=[
                WorkflowStep(id="1", app="system", action="return_result", params={"summary": "Done"}),
            ],
        )
        mock_runtime = MagicMock()
        mock_runtime.execute.return_value = "Done"
        mock_runtime.action_log = []
        mock_runtime.finalized = True
        mock_runtime.result_summary = "Done"

        mock_result = MagicMock()
        mock_result.summarize.return_value = "Done."
        orch._result_deliverer = mock_result

        with patch("core.agent_v2_orchestrator.get_virtual_desktop", return_value=mock_vd):
            with patch("core.agent_v2_orchestrator.WorkflowRuntime", return_value=mock_runtime):
                with patch("core.agent_v2_orchestrator.broadcast_sync"):
                    with patch("core.agent_v2_orchestrator.get_system_access") as mock_sys:
                        mock_sys.return_value = MagicMock()
                        with patch.object(orch._registry, "resolve", return_value=plan):
                            orch.initiate("info_gather", {"query": "test"})

        mock_vd.create_desktop.assert_called_once()
        mock_vd.switch_to_desktop.assert_called()
        mock_vd.close_desktop.assert_called_once_with("1")
