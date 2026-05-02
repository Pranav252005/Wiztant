"""Tests for core/agent.py AgentMemory."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from core.agent import AgentMemory


@pytest.fixture
def mem(tmp_path):
    """AgentMemory instance pointing at a temp data directory."""
    return AgentMemory(data_dir=tmp_path)


class TestRecordTask:
    def test_record_task_start_creates_record(self, mem):
        rec = mem.record_task_start("t1", "Open settings", "system")
        assert rec["task_id"] == "t1"
        assert rec["user_task"] == "Open settings"
        assert rec["task_type"] == "system"
        assert rec["status"] == "in_progress"

    def test_record_task_complete(self, mem):
        mem.record_task_start("t1", "Open settings", "system")
        mem.record_task_complete("t1", "undo-1", 1.23, {"detail": "ok"})
        task = mem.memory["tasks"][0]
        assert task["status"] == "completed"
        assert task["undo_id"] == "undo-1"
        assert task["execution_time_seconds"] == 1.23
        assert task["detail"] == "ok"
        assert "undo-1" in mem.memory["undo_stack"]

    def test_record_task_failed(self, mem):
        mem.record_task_start("t1", "Open settings", "system")
        mem.record_task_failed("t1", "pyautogui not found")
        task = mem.memory["tasks"][0]
        assert task["status"] == "failed"
        assert task["error"] == "pyautogui not found"

    def test_record_task_cancelled(self, mem):
        mem.record_task_start("t1", "Open settings", "system")
        mem.record_task_cancelled("t1")
        task = mem.memory["tasks"][0]
        assert task["status"] == "cancelled"

    def test_get_last_task(self, mem):
        mem.record_task_start("t1", "A", "system")
        mem.record_task_start("t2", "B", "system")
        mem.record_task_complete("t2", "u2", 1.0)
        last = mem.get_last_task()
        assert last["task_id"] == "t2"

    def test_get_last_task_none(self, mem):
        mem.record_task_start("t1", "A", "system")
        assert mem.get_last_task() is None

    def test_get_task_context(self, mem):
        mem.record_task_start("t1", "Open settings", "system")
        mem.record_task_complete("t1", "u1", 1.0)
        ctx = mem.get_task_context()
        assert "Open settings" in ctx
        assert "✓" in ctx

    def test_persistence(self, mem):
        mem.record_task_start("t1", "Open settings", "system")
        assert mem.history_file.exists()
        data = json.loads(mem.history_file.read_text())
        assert data["tasks"][0]["task_id"] == "t1"

    def test_load_existing(self, tmp_path):
        history_file = tmp_path / "agent_task_history.json"
        history_file.write_text(json.dumps({
            "session_id": "old-session",
            "tasks": [{"task_id": "old", "status": "completed"}],
            "current_chain": None,
            "undo_stack": [],
        }))
        mem = AgentMemory(data_dir=tmp_path)
        assert mem.memory["tasks"][0]["task_id"] == "old"


class TestUndoRingBuffer:
    def test_push_undo_basic(self, mem):
        mem.push_undo("t1", {"type": "click", "x": 10})
        ring = mem.memory["undo_ring"]
        assert len(ring) == 1
        assert ring[0]["task_id"] == "t1"

    def test_push_undo_overflow(self, mem):
        for i in range(17):
            mem.push_undo("t1", {"type": "click", "x": i})
        ring = mem.memory["undo_ring"]
        assert len(ring) == 16  # _RING_SIZE
        assert ring[0]["action"]["x"] == 1  # first entry (0) was dropped
        assert ring[-1]["action"]["x"] == 16

    def test_rollback_to_checkpoint_with_task_id(self, mem):
        for i in range(3):
            mem.push_undo("t1", {"type": "click", "x": i}, undo_hook="undo click")
        for i in range(2):
            mem.push_undo("t2", {"type": "type", "text": str(i)}, undo_hook="undo type")
        hooks = mem.rollback_to_checkpoint("t1")
        assert len(hooks) == 3
        assert all("undo click" in h for h in hooks)
        # t2 entries should remain
        ring = mem.memory["undo_ring"]
        assert len(ring) == 2
        assert ring[0]["task_id"] == "t2"

    def test_rollback_to_checkpoint_default_last(self, mem):
        for i in range(3):
            mem.push_undo("t1", {"type": "click", "x": i}, undo_hook="undo click")
        hooks = mem.rollback_to_checkpoint()
        assert len(hooks) == 3
        assert len(mem.memory["undo_ring"]) == 0

    def test_rollback_empty_ring(self, mem):
        hooks = mem.rollback_to_checkpoint("t1")
        assert hooks == []

    def test_rollback_returns_hooks_reversed(self, mem):
        mem.push_undo("t1", {"type": "a"}, undo_hook="hook-a")
        mem.push_undo("t1", {"type": "b"}, undo_hook="hook-b")
        hooks = mem.rollback_to_checkpoint("t1")
        assert hooks == ["hook-b", "hook-a"]

    def test_rollback_ignores_empty_hooks(self, mem):
        mem.push_undo("t1", {"type": "a"}, undo_hook="")
        mem.push_undo("t1", {"type": "b"}, undo_hook="hook-b")
        hooks = mem.rollback_to_checkpoint("t1")
        assert hooks == ["hook-b"]


class TestStoreUndoActions:
    def test_store_and_load(self, mem):
        mem.store_undo_actions("uid-1", "t1", [{"type": "click"}])
        assert mem.undo_file.exists()
        data = json.loads(mem.undo_file.read_text())
        assert "uid-1" in data
        assert data["uid-1"]["task_id"] == "t1"

    def test_store_appends(self, mem):
        mem.store_undo_actions("uid-1", "t1", [{"type": "click"}])
        mem.store_undo_actions("uid-2", "t2", [{"type": "type"}])
        data = json.loads(mem.undo_file.read_text())
        assert len(data) == 2
