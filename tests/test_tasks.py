"""Tests for core/tasks.py CRUD, parsing, and timezone handling."""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import tasks


@pytest.fixture(autouse=True)
def _isolate_tasks_json(tmp_path, monkeypatch):
    """Redirect tasks.json to a temp file so tests are hermetic."""
    test_path = tmp_path / "tasks.json"
    monkeypatch.setattr(tasks, "_TASKS_PATH", test_path)
    monkeypatch.setattr(tasks, "_LEGACY_TASKS_PATH", Path("/dev/null"))
    yield
    if test_path.exists():
        test_path.unlink()


def _task(text: str, due_at: str | None = None, status: str = "pending") -> dict:
    return {"text": text, "status": status, "due_at": due_at}


# ─── CRUD ─────────────────────────────────────────────────────────

def test_add_task_roundtrip():
    t = tasks.add_task("Buy milk", source="voice")
    assert t["text"] == "Buy milk"
    assert t["status"] == "pending"
    assert t["source"] == "voice"
    loaded = tasks.get_tasks()
    assert any(x["id"] == t["id"] for x in loaded)


def test_mark_done_moves_to_history():
    t = tasks.add_task("Write tests")
    done = tasks.mark_done(t["id"])
    assert done is not None
    assert done["status"] == "done"
    assert done["completed_at"] is not None
    hist = tasks.get_task_history()
    assert any(h["task_id"] == t["id"] for h in hist)


def test_toggle_status():
    t = tasks.add_task("Toggle me")
    tasks.toggle_status(t["id"])
    assert tasks.get_tasks()[0]["status"] == "done"
    tasks.toggle_status(t["id"])
    assert tasks.get_tasks()[0]["status"] == "pending"


def test_delete_task():
    t = tasks.add_task("Delete me")
    tasks.delete_task(t["id"])
    assert not any(x["id"] == t["id"] for x in tasks.get_tasks())


def test_add_subtask_links_parent():
    parent = tasks.add_task("Parent")
    child = tasks.add_subtask(parent["id"], "Child")
    assert child is not None
    assert child["parent_id"] == parent["id"]


def test_add_subtask_missing_parent():
    assert tasks.add_subtask("nonexistent", "Orphan") is None


# ─── Due-time parsing ─────────────────────────────────────────────

class TestParseDueTime:
    def test_am_pm(self):
        cleaned, due = tasks.parse_due_time("Call John by 3pm")
        assert "call john" in cleaned.lower()
        dt = datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone()
        assert dt.hour == 15

    def test_24h(self):
        cleaned, due = tasks.parse_due_time("Deploy at 14:30")
        dt = datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone()
        assert dt.hour == 14
        assert dt.minute == 30

    def test_tomorrow(self):
        cleaned, due = tasks.parse_due_time("Review by tomorrow 10am")
        dt = datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone()
        assert dt.date() == (datetime.now().astimezone().date() + timedelta(days=1))

    def test_no_match(self):
        cleaned, due = tasks.parse_due_time("Just a generic note")
        assert due is None
        assert cleaned == "Just a generic note"

    def test_invalid_hour_skipped(self):
        cleaned, due = tasks.parse_due_time("Meet at 25:00")
        assert due is None


# ─── split_separately ─────────────────────────────────────────────

def test_split_on_separately():
    result = tasks.split_separately("Buy milk, get eggs separately")
    assert result is not None
    assert len(result) >= 2
    assert any("milk" in r.lower() for r in result)
    assert any("eggs" in r.lower() for r in result)


def test_split_on_multiple_due_markers():
    text = "Email team by 10am and review PR by 2pm"
    result = tasks.split_separately(text)
    assert result is not None
    assert len(result) == 2


def test_no_split_when_single_marker():
    assert tasks.split_separately("One thing by 5pm") is None


def test_no_split_when_no_marker():
    assert tasks.split_separately("Just a note") is None


# ─── default_noon_due_at ──────────────────────────────────────────

def test_noon_is_future():
    due = tasks.default_noon_due_at()
    dt = datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone()
    assert dt.hour == 12
    assert dt > datetime.now().astimezone() or dt.date() > datetime.now().astimezone().date()


# ─── Timezone handling ────────────────────────────────────────────

def test_get_due_today_undone_respects_timezone():
    today_local = datetime.now().astimezone()
    due_str = today_local.replace(hour=10, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat()
    tasks.add_task("Morning standup", due_at=due_str)
    found = tasks.get_due_today_undone()
    assert any("standup" in t["text"].lower() for t in found)


def test_get_due_today_ignores_done():
    today_local = datetime.now().astimezone()
    due_str = today_local.replace(hour=10, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat()
    t = tasks.add_task("Done thing", due_at=due_str)
    tasks.mark_done(t["id"])
    found = tasks.get_due_today_undone()
    assert not any(t["id"] == x["id"] for x in found)


# ─── reschedule_to_tomorrow ───────────────────────────────────────

def test_reschedule_preserves_time():
    now_local = datetime.now().astimezone()
    due = now_local.replace(hour=9, minute=30, second=0, microsecond=0).astimezone(timezone.utc).isoformat()
    t = tasks.add_task("Move me", due_at=due)
    assert tasks.reschedule_to_tomorrow(t["id"])
    moved = [x for x in tasks.get_tasks() if x["id"] == t["id"]][0]
    new_due = datetime.fromisoformat(moved["due_at"].replace("Z", "+00:00")).astimezone()
    assert new_due.hour == 9
    assert new_due.minute == 30
    assert new_due.date() == (now_local.date() + timedelta(days=1))
    assert moved.get("carried_over") is True


# ─── carried_over / failed ────────────────────────────────────────

def test_mark_failed():
    t = tasks.add_task("Failed task")
    assert tasks.mark_failed(t["id"])
    updated = [x for x in tasks.get_tasks() if x["id"] == t["id"]][0]
    assert updated["failed"] is True
    assert updated["carried_over"] is False


def test_get_carried_over_undone():
    t = tasks.add_task("Carried")
    tasks.reschedule_to_tomorrow(t["id"])
    carried = tasks.get_carried_over_undone()
    assert any(x["id"] == t["id"] for x in carried)


# ─── Task mention / smart detection patterns ──────────────────────

class TestTaskMentionPatterns:
    # ── Explicit prefixes: fast path, extracted candidate returned ──

    def test_prefix_this_is_a_task(self):
        result = tasks.extract_task_mention("this is a task buy milk")
        assert result is not None
        assert result == "buy milk"

    def test_prefix_add_task(self):
        result = tasks.extract_task_mention("add task call John by 5pm")
        assert result is not None
        assert "call John" in result

    def test_prefix_create_a_task_for(self):
        result = tasks.extract_task_mention("create a task for the Q4 report")
        assert result is not None
        assert "Q4 report" in result

    def test_prefix_task_colon(self):
        result = tasks.extract_task_mention("task: finish the deck")
        assert result is not None
        assert result == "finish the deck"

    def test_prefix_todo_colon(self):
        result = tasks.extract_task_mention("todo: email the team")
        assert result is not None
        assert result == "email the team"

    # ── Borderline mentions: raw text returned for LLM verification ──

    def test_trailing_this_is_a_task_returns_raw(self):
        # Was previously extracted directly; now returned raw for LLM gate
        result = tasks.extract_task_mention("buy groceries this is a task")
        assert result == "buy groceries this is a task"

    def test_casual_task_mention_returns_raw(self):
        result = tasks.extract_task_mention("I have a lot of tasks today")
        assert result == "I have a lot of tasks today"

    def test_that_sounds_like_a_task_returns_raw(self):
        result = tasks.extract_task_mention("That sounds like a task")
        assert result == "That sounds like a task"

    # ── No match: normal dictation ──

    def test_no_false_positive_on_normal_text(self):
        result = tasks.extract_task_mention("just some normal dictation text")
        assert result is None

    def test_no_match_without_task_word(self):
        # Natural language without "task"/"todo" must NOT trigger
        result = tasks.extract_task_mention("I need to call John")
        assert result is None

    def test_no_match_remind_me_without_task_word(self):
        result = tasks.extract_task_mention("Remind me to call mom")
        assert result is None

    def test_no_match_action_plus_time_without_task_word(self):
        result = tasks.extract_task_mention("Call John by 5pm")
        assert result is None

    def test_no_match_implicit_future_without_task_word(self):
        result = tasks.extract_task_mention("I will finish the report tomorrow")
        assert result is None
