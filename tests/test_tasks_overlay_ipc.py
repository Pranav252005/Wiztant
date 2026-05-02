"""Smoke test for task add round-trip through the WebSocket bridge."""

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import ws_bridge
from core import tasks


@pytest.fixture(autouse=True)
def _isolate_tasks_json(tmp_path, monkeypatch):
    test_path = tmp_path / "tasks.json"
    monkeypatch.setattr(tasks, "_TASKS_PATH", test_path)
    monkeypatch.setattr(tasks, "_LEGACY_TASKS_PATH", Path("/dev/null"))
    yield
    if test_path.exists():
        test_path.unlink()


class _FakeClient:
    """Mock WebSocket client that records every broadcast."""
    def __init__(self):
        self.messages = []

    async def send(self, payload: str):
        self.messages.append(json.loads(payload))


@pytest.fixture
def fake_client(monkeypatch):
    client = _FakeClient()
    ws_bridge._clients.add(client)
    yield client
    ws_bridge._clients.discard(client)


def test_tasks_add_via_broadcast(fake_client, monkeypatch):
    """Simulate the overlay sending tasks/add and verify broadcast."""
    captured = []

    def _capture_broadcast(data: dict):
        captured.append(data)
        fake_client.messages.append(data)

    monkeypatch.setattr(ws_bridge, "broadcast_sync", _capture_broadcast)

    msg = {
        "type": "tasks/add",
        "text": "Write cross-platform tests",
        "source": "typed",
        "due_at": None,
    }

    # Directly exercise the handler logic (skip WebSocket framing)
    ws_bridge._handle_tasks_add(msg)

    # Wait for the background thread to finish
    time.sleep(0.3)

    # Verify persistence
    stored = tasks.get_tasks()
    assert any(t["text"] == "Write cross-platform tests" for t in stored)

    # Verify broadcast was captured
    updates = [m for m in captured if m.get("type") == "tasks/update"]
    assert len(updates) >= 1
    payload = updates[-1].get("payload", [])
    assert any(t["text"] == "Write cross-platform tests" for t in payload)


def test_tasks_toggle_via_broadcast(fake_client, monkeypatch):
    t = tasks.add_task("Toggle via IPC")
    msg = {"type": "tasks/toggle_status", "task_id": t["id"]}

    ws_bridge._handle_tasks_toggle(msg)
    time.sleep(0.3)

    stored = tasks.get_tasks()
    updated = next(x for x in stored if x["id"] == t["id"])
    assert updated["status"] == "done"


def test_tasks_delete_via_broadcast(fake_client, monkeypatch):
    t = tasks.add_task("Delete via IPC")
    msg = {"type": "tasks/delete", "task_id": t["id"]}

    ws_bridge._handle_tasks_delete(msg)
    time.sleep(0.3)

    stored = tasks.get_tasks()
    assert not any(x["id"] == t["id"] for x in stored)
