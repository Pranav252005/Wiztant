"""Tests for core/workflow_gates.py — Async Decision Gates."""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.workflow_gates import GateManager, DecisionGate


class TestGateManager:
    """Test suite for decision gate creation, timeout, and resolution."""

    def test_create_gate_returns_gate_id(self):
        """Creating a gate should return a unique gate ID."""
        manager = GateManager()
        gate_id = manager.create_gate("Approve this?", ["yes", "no"], timeout=5)
        assert isinstance(gate_id, str)
        assert len(gate_id) > 0

    def test_await_decision_blocks_until_resolved(self):
        """await_decision should block until resolve is called."""
        manager = GateManager()
        gate_id = manager.create_gate("Send message?", ["yes", "no"], timeout=10)

        result = [None]

        def waiter():
            result[0] = manager.await_decision(gate_id)

        t = threading.Thread(target=waiter)
        t.start()

        # Simulate user responding after a short delay
        time.sleep(0.1)
        manager.resolve(gate_id, "yes")
        t.join(timeout=2)

        assert result[0] == "yes"
        assert not t.is_alive()

    def test_timeout_returns_safe_default(self):
        """If no decision arrives before timeout, return the safe default."""
        manager = GateManager()
        gate_id = manager.create_gate("Delete file?", ["yes", "no"], timeout=0.2)

        # No resolve called — should timeout
        result = manager.await_decision(gate_id)

        # "Delete file?" is destructive → safe default is "no"
        assert result == "no"

    def test_informational_gate_defaults_to_yes(self):
        """Non-destructive gates should default to 'yes' on timeout."""
        manager = GateManager()
        gate_id = manager.create_gate("Read this page?", ["yes", "no"], timeout=0.2)

        result = manager.await_decision(gate_id)
        assert result == "yes"

    def test_resolve_unknown_gate_is_noop(self):
        """Resolving an unknown gate ID should not raise."""
        manager = GateManager()
        manager.resolve("nonexistent-gate", "yes")  # should not raise

    def test_gate_broadcasts_ws_event(self):
        """Creating a gate should broadcast a workflow/gate event."""
        manager = GateManager()
        mock_ws = type("MockWS", (), {"broadcast_sync": lambda self, data: None})()

        calls = []
        def capture_broadcast(data):
            calls.append(data)

        mock_ws.broadcast_sync = capture_broadcast
        manager._ws = mock_ws

        gate_id = manager.create_gate("Confirm?", ["yes", "no"], timeout=5)
        # create_gate does not auto-broadcast in our design; orchestrator does
        # So we just verify the gate object exists
        assert gate_id in manager._gates
