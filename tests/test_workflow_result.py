"""Tests for core/workflow_result.py — Workflow Result Summarizer & Delivery."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.workflow_result import WorkflowResult


class TestWorkflowResult:
    """Test suite for result summarization and delivery."""

    def test_summarize_extracts_ticket_number(self):
        """Summarizer should extract the ticket number from the action log."""
        action_log = [
            {"action": "open_app", "params": {"app_name": "chrome"}, "result": "chrome"},
            {"action": "navigate_to", "params": {"url": "https://jira.example.com"}, "result": True},
            {"action": "read_screen", "params": {}, "result": "Ticket PROJ-42 created successfully"},
            {"action": "return_result", "params": {"summary": "Done"}, "result": "Done"},
        ]
        summarizer = WorkflowResult()
        mock_summary = "Created ticket PROJ-42 in Jira."

        with patch("core.workflow_result.call_api", return_value=mock_summary):
            result = summarizer.summarize(action_log)

        assert "PROJ-42" in result

    def test_deliver_copies_to_clipboard(self):
        """Delivery should copy the result to system clipboard."""
        summarizer = WorkflowResult()
        mock_sys = MagicMock()
        mock_ws = MagicMock()

        summarizer.deliver("Ticket PROJ-42 created.", mock_ws, mock_sys)

        mock_sys.set_clipboard.assert_called_once_with("Ticket PROJ-42 created.")

    def test_deliver_broadcasts_to_overlay(self):
        """Delivery should broadcast workflow/result event via WebSocket."""
        summarizer = WorkflowResult()
        mock_sys = MagicMock()
        mock_ws = MagicMock()

        summarizer.deliver("Ticket PROJ-42 created.", mock_ws, mock_sys)

        mock_ws.broadcast_sync.assert_called()
        # Check all calls for the workflow/result event
        result_calls = [c[0][0] for c in mock_ws.broadcast_sync.call_args_list if c[0][0].get("type") == "workflow/result"]
        assert len(result_calls) == 1
        assert "PROJ-42" in result_calls[0]["summary"]

    def test_failure_log_produces_actionable_summary(self):
        """A failed workflow should produce an actionable error summary."""
        action_log = [
            {"action": "open_app", "params": {"app_name": "chrome"}, "result": "chrome"},
            {"action": "navigate_to", "params": {"url": "https://jira.example.com"}, "result": False},
        ]
        summarizer = WorkflowResult()
        mock_summary = "Failed to open Jira. The page may be down or the URL may be incorrect. Try again later."

        with patch("core.workflow_result.call_api", return_value=mock_summary):
            result = summarizer.summarize(action_log)

        assert "failed" in result.lower() or "error" in result.lower() or "down" in result.lower()

    def test_summarize_handles_empty_log(self):
        """An empty action log should still return a summary."""
        summarizer = WorkflowResult()
        mock_summary = "No actions were recorded."

        with patch("core.workflow_result.call_api", return_value=mock_summary):
            result = summarizer.summarize([])

        assert result == "No actions were recorded."
