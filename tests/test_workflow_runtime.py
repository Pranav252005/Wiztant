"""Tests for core/workflow_runtime.py — Workflow Runtime restricted action executor."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.workflow_runtime import WorkflowRuntime, WorkflowActionBlocked


class TestWorkflowRuntime:
    """Test suite for WorkflowRuntime action restriction and execution."""

    def test_blocked_file_write_raises(self):
        """create_file must raise WorkflowActionBlocked."""
        runtime = WorkflowRuntime()
        with pytest.raises(WorkflowActionBlocked):
            runtime.execute("create_file", path="/tmp/test.txt", content="hello")

    def test_blocked_git_commit_raises(self):
        """git_commit must raise WorkflowActionBlocked."""
        runtime = WorkflowRuntime()
        with pytest.raises(WorkflowActionBlocked):
            runtime.execute("git_commit", message="test")

    def test_blocked_shell_execution_raises(self):
        """execute_shell must raise WorkflowActionBlocked."""
        runtime = WorkflowRuntime()
        with pytest.raises(WorkflowActionBlocked):
            runtime.execute("execute_shell", command="ls -la")

    def test_blocked_edit_file_raises(self):
        """edit_file must raise WorkflowActionBlocked."""
        runtime = WorkflowRuntime()
        with pytest.raises(WorkflowActionBlocked):
            runtime.execute("edit_file", path="main.py", content="new code")

    def test_allowed_open_app_succeeds(self):
        """open_app should delegate to system access when allowed."""
        runtime = WorkflowRuntime()
        mock_sys = MagicMock()
        mock_sys.launch_app.return_value = "slack"

        with patch("core.workflow_runtime.get_system_access", return_value=mock_sys):
            result = runtime.execute("open_app", app_name="slack")

        assert result == "slack"
        mock_sys.launch_app.assert_called_once_with(app_name="slack")
        assert len(runtime.action_log) == 1
        assert runtime.action_log[0]["action"] == "open_app"

    def test_allowed_click_succeeds(self):
        """click should delegate to system access when allowed."""
        runtime = WorkflowRuntime()
        mock_sys = MagicMock()
        mock_sys.click.return_value = (True, "clicked")

        with patch("core.workflow_runtime.get_system_access", return_value=mock_sys):
            result = runtime.execute("click", x=100, y=200)

        assert result == (True, "clicked")
        mock_sys.click.assert_called_once_with(x=100, y=200)

    def test_ask_human_returns_gate_request(self):
        """ask_human should return a GateRequest, not block."""
        runtime = WorkflowRuntime()
        result = runtime.execute("ask_human", question="Send this message?", timeout=60)

        assert result is not None
        assert result["type"] == "gate_request"
        assert result["question"] == "Send this message?"
        assert result["timeout"] == 60
        assert len(runtime.action_log) == 1

    def test_return_result_finalizes_run(self):
        """return_result should mark the run as finalized and store the summary."""
        runtime = WorkflowRuntime()
        result = runtime.execute("return_result", summary="Ticket PROJ-42 created.")

        assert result == "Ticket PROJ-42 created."
        assert runtime.finalized is True
        assert runtime.result_summary == "Ticket PROJ-42 created."
        assert len(runtime.action_log) == 1
        assert runtime.action_log[0]["action"] == "return_result"

    def test_action_log_accumulates(self):
        """Multiple allowed actions should accumulate in the log."""
        runtime = WorkflowRuntime()
        mock_sys = MagicMock()
        mock_sys.launch_app.return_value = "browser"
        mock_sys.type_text.return_value = (True, "typed")

        with patch("core.workflow_runtime.get_system_access", return_value=mock_sys):
            runtime.execute("open_app", app_name="browser")
            runtime.execute("type", text="hello world")

        assert len(runtime.action_log) == 2
        assert runtime.action_log[0]["action"] == "open_app"
        assert runtime.action_log[1]["action"] == "type"
